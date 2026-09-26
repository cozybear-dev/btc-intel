"""Explainable risk verdict: a level plus the plain-English reasons that produced it."""

from __future__ import annotations

from typing import Any

from btcintel.analysis.models import ClusterSummary, Exposure, Reason, Verdict
from btcintel.catalog.schema import RISK_ORDER
from btcintel.labels.taxonomy import Taxonomy

HIGH_SHARE = 0.10  # share of traced value involving high/severe entities that makes an address high risk
MEDIUM_SHARE = 0.25  # share involving medium entities (CoinJoin, gambling, swappers…) that makes it medium
LOW_COVERAGE = 0.5  # below this share of value traced to an endpoint the verdict is low confidence
LEVELS = ["none", "low", "medium", "high", "severe"]
MAX_LABEL_REASONS = 3
_WORDS = {"backward": ("Received", "from", "incoming", "came from"),
          "forward": ("Sent", "to", "outgoing", "went to")}


def btc(sats: float) -> str:
    return f"{sats / 100_000_000:.8f}".rstrip("0").rstrip(".") + " BTC"


def pct(share: float) -> str:
    return f"{share * 100:.1f}%" if share < 0.1 else f"{share * 100:.0f}%"


def _tag_risk(taxonomy: Taxonomy, tag: dict[str, Any]) -> str:
    return max(taxonomy.risk(tag.get("category")), taxonomy.risk(tag.get("abuse")), key=RISK_ORDER.__getitem__)


def _names(labels: list[str]) -> str:
    return ", ".join(list(dict.fromkeys(labels))[:3])


def label_reasons(address: str, info: dict[str, Any], cluster: ClusterSummary | None,
                  taxonomy: Taxonomy) -> list[Reason]:
    reasons: list[Reason] = []
    seen: set[str] = set()
    for tag in info.get("tags", []):
        level = _tag_risk(taxonomy, tag)
        own = tag.get("address") == address
        # the address's own labels always say who it is; inherited ones only count when risky
        if (not own and RISK_ORDER[level] < RISK_ORDER["medium"]) or tag["label"] in seen:
            continue
        seen.add(tag["label"])
        what = f"{tag['label']} ({tag.get('abuse') or tag.get('category')}, {tag.get('pack') or tag.get('source')})"
        if own:
            reasons.append(Reason(level=level, rule="own_label", text=f"Labeled {what}"))
            continue
        where = f"Its co-spend cluster ({cluster.size} addresses)" if cluster else "Its co-spend cluster"
        text = f"{where} includes {what}"
        if cluster and cluster.conflicts:
            level = LEVELS[max(0, LEVELS.index(level) - 1)]
            text += "; the cluster has conflicting labels, so this may be a merge error"
        reasons.append(Reason(level=level, rule="cluster_label", text=text))
    reasons.sort(key=lambda r: -RISK_ORDER[r.level])
    return reasons[:MAX_LABEL_REASONS]


def _base(e: Exposure) -> float:
    """The value an exposure's shares refer to: the traced total, or what the trace reached when that
    is more (every receipt in the window was the address's own change, so the total is 0)."""
    return max(e.total, sum(b.amount for b in e.buckets))


def exposure_reasons(e: Exposure) -> list[Reason]:
    failed = [Reason(level="none", rule="trace_failed", text=(
        f"{'Sources' if e.direction == 'backward' else 'Destinations'} could not be traced: {e.error}"))] if e.error else []
    if not e.buckets:
        return failed
    verb, prep, noun, went = _WORDS[e.direction]
    labeled = [b for b in e.buckets if b.kind == "labeled"]
    reasons = [
        Reason(level="severe", rule="direct_severe",
               text=f"{verb} {btc(b.amount)} directly {prep} {b.label} ({b.key}{', ' + b.source if b.source else ''})")
        for b in labeled if b.risk == "severe" and b.min_hops == 1
    ]
    risky = [b for b in labeled if RISK_ORDER[b.risk] >= RISK_ORDER["high"]]
    if risky:
        share = sum(b.share for b in risky)
        hops = max(b.min_hops or 0 for b in risky)
        level, rule = ("high", "high_share") if share >= HIGH_SHARE else ("medium", "high_minor")
        reasons.append(Reason(level=level, rule=rule, text=(
            f"{pct(share)} of {noun} funds ({btc(sum(b.amount for b in risky))}) {went} high-risk entities: "
            f"{_names([b.label for b in risky])}{f' (within {hops} hops)' if hops else ''}")))
    medium = [b for b in e.buckets if b.kind in ("labeled", "coinjoin") and b.risk == "medium"]
    if medium:
        share = sum(b.share for b in medium)
        level, rule = ("medium", "medium_share") if share >= MEDIUM_SHARE else ("low", "medium_minor")
        reasons.append(Reason(level=level, rule=rule, text=(
            f"{pct(share)} of {noun} funds {went} medium-risk services: {_names([b.label for b in medium])}")))
    if labeled and not risky and not medium:
        reasons.append(Reason(level="low", rule="low_only", text=(
            f"{noun.capitalize()} funds {went} only low-risk known entities: {_names([b.label for b in labeled])}")))
    return reasons + failed


def coverage_line(exposures: list[Exposure], hops: int) -> tuple[str, float | None]:
    """Human coverage line and the overall share of value traced to an endpoint (None: nothing to trace)."""
    if not exposures:
        return "Tracing in progress…", None
    bases = [_base(e) for e in exposures]
    total = sum(bases)
    if not total:
        return "No incoming funds in the analysed history, so there was nothing to trace", None
    resolved = sum(e.resolved_share * base for e, base in zip(exposures, bases, strict=True)) / total
    return (f"Traced {pct(resolved)} of funds to an endpoint within {hops} hops; {pct(1 - resolved)} not reached",
            resolved)


def low_confidence(exposures: list[Exposure], resolved: float | None) -> bool:
    """Too little traced overall, a direction that failed, or a direction mostly not reached."""
    return ((resolved is not None and resolved < LOW_COVERAGE)
            or any(e.error for e in exposures)
            or any(_base(e) and e.resolved_share < LOW_COVERAGE for e in exposures))


def build_verdict(address: str, info: dict[str, Any], cluster: ClusterSummary | None, exposures: list[Exposure],
                  *, taxonomy: Taxonomy, hops: int, final: bool) -> Verdict:
    reasons = label_reasons(address, info, cluster, taxonomy)
    for e in exposures:
        reasons += exposure_reasons(e)
    coverage, resolved = coverage_line(exposures, hops) if final else ("Tracing in progress…", None)
    low = final and low_confidence(exposures, resolved)
    if all(r.rule == "trace_failed" for r in reasons):
        if not final:
            text = "No labels on this address; tracing its funds…"
        elif low and resolved is not None:
            text = f"No known entity found within {hops} hops (only {pct(resolved)} of funds traced)"
        else:
            text = f"No known entity found within {hops} hops"
        reasons.insert(0, Reason(level="none", rule="nothing", text=text))
    reasons.sort(key=lambda r: -RISK_ORDER[r.level])
    return Verdict(level=reasons[0].level, final=final, low_confidence=low, coverage=coverage, reasons=reasons)
