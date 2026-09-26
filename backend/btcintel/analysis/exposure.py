"""Where traced value ended: stops grouped into exposure buckets that add up to the traced total."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from btcintel.analysis.models import Bucket, Direction, Exposure
from btcintel.catalog.schema import RISK_ORDER
from btcintel.labels.taxonomy import Taxonomy
from btcintel.trace.engine import TraceResult
from btcintel.trace.graph import Stop

RESOLVED = frozenset({"labeled", "own_cluster", "coinjoin", "unspent", "coinbase"})
LIMIT_LABELS = {"max_hops": "Beyond the hop limit", "min_value": "Below the minimum value",
                "max_txs": "Beyond the transaction limit", "peel_off": "Peeled off"}
REMAINDER_LABEL = "Fees or not reached (budget)"
MAX_NODES = 5


def _bucket_for(stop: Stop, nodes: dict[str, dict[str, Any]], own_cluster: Callable[[str], bool],
                taxonomy: Taxonomy) -> Bucket:
    """An empty bucket describing where this stop's value ended."""
    if stop.reason == "labeled":
        data = nodes.get(stop.node, {})
        key = data.get("stop_category") or data.get("category") or "unknown"
        tag = next((t for t in data.get("tags", []) if key in (t.get("abuse"), t.get("category"))), {})
        own = own_cluster(stop.node.removeprefix("addr:"))
        return Bucket(kind="own_cluster" if own else "labeled", key=key,
                      label=tag.get("label") or data.get("label") or key,
                      risk=data.get("risk") or taxonomy.risk(key), source=tag.get("pack"))
    if stop.reason == "coinjoin":
        kind = stop.detail or "unknown"
        return Bucket(kind="coinjoin", key=kind, label=f"CoinJoin ({kind})", risk=taxonomy.risk("coinjoin"))
    if stop.reason == "unspent":
        return Bucket(kind="unspent", key="unspent", label="Still unspent")
    if stop.reason == "coinbase":
        return Bucket(kind="coinbase", key="coinbase", label="Newly mined coins")
    return Bucket(kind="limits", key=stop.reason, label=LIMIT_LABELS[stop.reason])


def compute_exposure(direction: Direction, result: TraceResult, total: float, *, taxonomy: Taxonomy,
                     own_cluster: Callable[[str], bool]) -> Exposure:
    nodes = {n.id: n.data for n in result.nodes}
    groups: dict[tuple[str, str, str], Bucket] = {}
    for stop in result.stops:
        b = _bucket_for(stop, nodes, own_cluster, taxonomy)
        k = (b.kind, b.key, b.label)
        g = groups.setdefault(k, b)
        hops = [h for h in (g.min_hops, stop.hops) if h is not None]
        keep = stop.node in g.nodes or len(g.nodes) >= MAX_NODES
        groups[k] = g.model_copy(update={"amount": g.amount + stop.taint, "min_hops": min(hops) if hops else None,
                                         "nodes": g.nodes if keep else [*g.nodes, stop.node]})
    buckets = list(groups.values())
    reached = sum(b.amount for b in buckets)
    if total - reached >= 1:
        buckets.append(Bucket(kind="remainder", key="remainder", label=REMAINDER_LABEL, amount=total - reached))
    base = max(total, reached)
    buckets = [b.model_copy(update={"share": b.amount / base if base else 0.0}) for b in buckets]
    buckets.sort(key=lambda b: (b.kind == "remainder", -RISK_ORDER[b.risk], -b.amount))
    resolved = sum(b.amount for b in buckets if b.kind in RESOLVED)
    return Exposure(direction=direction, total=total, buckets=buckets,
                    resolved_share=resolved / base if base else 0.0, incomplete=result.incomplete,
                    reason=result.reason, calls_used=result.calls_used)


def failed_exposure(direction: Direction, total: float, error: str) -> Exposure:
    """A trace that could not run: all of its value is 'not reached'."""
    buckets = [Bucket(kind="remainder", key="remainder", label=REMAINDER_LABEL, amount=total, share=1.0)] if total else []
    return Exposure(direction=direction, total=total, buckets=buckets, resolved_share=0.0, incomplete=True,
                    reason=error, error=error)
