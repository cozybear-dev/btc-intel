"""Automatic address analysis as one job: profile, cluster, sources and destinations, verdict."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from contextlib import aclosing
from dataclasses import replace
from typing import Any

from btcintel.analysis.exposure import compute_exposure, failed_exposure
from btcintel.analysis.models import (
    AnalysisPolicy,
    AnalysisReport,
    ClusterSummary,
    Direction,
    Exposure,
)
from btcintel.analysis.profile import build_profile
from btcintel.analysis.report import to_markdown
from btcintel.analysis.verdict import build_verdict
from btcintel.catalog.schema import RISK_ORDER
from btcintel.chain.budget import CallBudget, budget_scope
from btcintel.chain.errors import ChainError
from btcintel.chain.source import ChainSource
from btcintel.chain.validate import normalize_address
from btcintel.cluster.expand import ExpandPolicy, ExpandResult, cluster_tags, expand_cluster
from btcintel.cluster.unionfind import UnionFind
from btcintel.labels.lookup import AddressInfo, LabelLookup
from btcintel.labels.store import TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.trace.engine import TracePolicy, TraceResult, TraceSeed, trace
from btcintel.trace.graph import Emit

TOP_CLUSTER_LABELS = 5
PROFILE_TAGS = 10


def _ignore(event: dict[str, Any]) -> None:
    return None


def analysis_stop_categories(taxonomy: Taxonomy) -> list[str]:
    """Analysis traces stop at every labeled entity, abuse labels included, so each traced satoshi
    ends at exactly one endpoint and the exposure shares add up."""
    return sorted(set(taxonomy.categories) - {"unknown"})


class _AnalysisLabels(LabelLookup):
    """Label lookup for the analysis traces: the seed's untagged cluster siblings do not stop them.

    Every cluster sibling inherits the seed's tags, so with the analysis stop set a labeled seed's
    change and consolidation addresses would stop its trace at hop 1 as "own cluster" and the real
    counterparties would never be reached. An address in the seed's current cluster with no tags of
    its own is therefore traced through; one with its own tags still stops (as "own cluster").
    """

    def __init__(self, tags: TagStore, taxonomy: Taxonomy, uf: UnionFind, stop_categories: list[str],
                 seed: str) -> None:
        super().__init__(tags, taxonomy, uf, stop_categories)
        self.cluster_uf = uf
        self.seed = seed

    def lookup(self, address: str) -> AddressInfo:
        info = super().lookup(address)
        own_tags = any(t.address == info.address for t in info.tags)
        if (info.stop_category and not own_tags and info.cluster is not None
                and info.cluster == self.cluster_uf.root_of(self.seed)):
            return replace(info, stop_category=None)
        return info


def label_views(info: AddressInfo, taxonomy: Taxonomy) -> tuple[dict[str, Any], dict[str, Any]]:
    """The address's label info for the profile (top PROFILE_TAGS tags) and for the verdict (every
    tag), with tags riskiest first. AddressInfo.to_dict() keeps the first 10 in confidence order,
    which would hide a low-confidence severe tag behind well-attested low-risk ones."""
    ranked = sorted(info.tags, key=lambda t: -RISK_ORDER[taxonomy.risk_of_tag(t)])  # stable: confidence order kept
    full = {**info.to_dict(), "tags": [t.model_dump() for t in ranked]}
    return {**full, "tags": full["tags"][:PROFILE_TAGS]}, full


def summarize_cluster(result: ExpandResult, uf: UnionFind, tags: TagStore, taxonomy: Taxonomy) -> ClusterSummary:
    counts = Counter((t.label, t.category, t.abuse) for t in cluster_tags(result.root, uf, tags))

    def risk(key: tuple[str, str, str | None]) -> int:
        return max(RISK_ORDER[taxonomy.risk(key[1])], RISK_ORDER[taxonomy.risk(key[2])])

    ranked = sorted(counts.items(), key=lambda kv: (-risk(kv[0]), -kv[1]))  # riskiest, then most common
    top = [{"label": label, "category": category, "abuse": abuse, "count": n}
           for (label, category, abuse), n in ranked[:TOP_CLUSTER_LABELS]]
    return ClusterSummary(root=result.root, size=result.size, partial=result.partial, capped=result.capped,
                          conflicts=result.conflicts, top_labels=top, calls_used=result.calls_used)


async def analyze_address(address: str, policy: AnalysisPolicy, *, chain: ChainSource, tags: TagStore,
                          uf: UnionFind, taxonomy: Taxonomy, emit: Emit | None = None) -> AnalysisReport:
    address = normalize_address(address)
    send = emit or _ignore
    calls = 0

    def section(name: str, data: Any) -> None:
        send({"type": "section", "name": name, "data": data.model_dump()})

    def progress(stage: str) -> None:
        send({"type": "progress", "stage": stage, "calls": calls})

    # 1. Profile: a few calls. The fetched tx bodies are cached, so the traces reuse them.
    budget = CallBudget(policy.history_txs // 25 + 10)
    with budget_scope(budget):
        stats = await chain.get_address(address)
        async with aclosing(chain.iter_address_txs(address, policy.history_txs)) as txs:
            history = [tx async for tx in txs]
    calls = budget.used
    shown, all_labels = label_views(LabelLookup(tags, taxonomy, uf).lookup(address), taxonomy)
    profile = build_profile(address, stats, history, shown)
    section("profile", profile)
    section("verdict", build_verdict(address, all_labels, None, [], taxonomy=taxonomy,
                                     hops=policy.trace_hops, final=False))
    progress("profile")

    # 2. Cluster, sources and destinations run concurrently, each inside its own call budget.
    stop_categories = analysis_stop_categories(taxonomy)
    trace_labels = _AnalysisLabels(tags, taxonomy, uf, stop_categories, address)

    def graph_event(event: dict[str, Any]) -> None:
        if event["type"] != "done":  # the analysis sends one "done" of its own at the end
            send(event)

    async def run_cluster() -> ClusterSummary:
        nonlocal calls
        try:
            result = await expand_cluster(address, chain, uf, tags, ExpandPolicy(
                max_addresses=policy.cluster_addresses, max_calls=policy.cluster_calls,
                max_txs_per_address=policy.history_txs))
            summary = summarize_cluster(result, uf, tags, taxonomy)
        except ChainError as e:
            summary = ClusterSummary(root=address, size=1, partial=True, capped=False,
                                     error=f"{type(e).__name__}: {e}")
        calls += summary.calls_used
        section("cluster", summary)
        progress("cluster")
        return summary

    async def run_trace(direction: Direction) -> TraceResult | str:
        nonlocal calls
        # Seeding puts every history tx paying the address into the trace graph, so the tx cap
        # allows for that history on top of trace_txs; the call budget still bounds the work.
        tp = TracePolicy(direction=direction, max_hops=policy.trace_hops,
                         max_txs=policy.trace_txs + policy.history_txs,
                         max_calls=policy.trace_calls, min_value_sats=policy.min_value_sats,
                         taint_model="haircut", stop_categories=stop_categories,
                         max_address_txs=policy.history_txs)
        try:
            result = await trace(TraceSeed(address=address), tp, chain=chain, labels=trace_labels,
                                 emit=graph_event)
        except ChainError as e:  # e.g. NotFound mid-trace; the other stages still complete
            progress(direction)
            return f"{type(e).__name__}: {e}"
        calls += result.calls_used
        progress(direction)
        return result

    cluster, back, fwd = await asyncio.gather(run_cluster(), run_trace("backward"), run_trace("forward"))

    # 3. Exposure per direction. Value ending inside the address's own cluster is not exposure.
    root = uf.root_of(address)

    def own_cluster(other: str) -> bool:
        return root is not None and uf.root_of(other) == root

    def exposure(direction: Direction, result: TraceResult | str) -> Exposure:
        if isinstance(result, str):
            return failed_exposure(direction, profile.received_external, result)
        return compute_exposure(direction, result, profile.received_external, taxonomy=taxonomy,
                                own_cluster=own_cluster)

    sources, destinations = exposure("backward", back), exposure("forward", fwd)
    section("sources", sources)
    section("destinations", destinations)

    # 4. Final verdict, with labels re-read now that the cluster may have grown.
    shown, all_labels = label_views(LabelLookup(tags, taxonomy, uf).lookup(address), taxonomy)
    profile = profile.model_copy(update={"info": shown})
    section("profile", profile)
    verdict = build_verdict(address, all_labels, cluster, [sources, destinations], taxonomy=taxonomy,
                            hops=policy.trace_hops, final=True)
    section("verdict", verdict)
    report = AnalysisReport(address=address, depth=policy.depth, generated_at=time.time(), profile=profile,
                            cluster=cluster, sources=sources, destinations=destinations, verdict=verdict,
                            calls_used=calls)
    report = report.model_copy(update={"markdown": to_markdown(report)})
    stopped = [e.reason for e in (sources, destinations) if e.incomplete and e.reason]
    send({"type": "done", "incomplete": bool(stopped), "reason": "; ".join(stopped) or None, "calls_used": calls})
    return report
