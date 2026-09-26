"""Markdown rendering of an analysis report (CLI output and case notes)."""

from __future__ import annotations

from datetime import UTC, datetime

from btcintel.analysis.models import AnalysisReport, Exposure
from btcintel.analysis.verdict import btc, pct


def _date(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d") if ts else "—"


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|")


def _exposure_lines(title: str, e: Exposure | None) -> list[str]:
    lines = [f"## {title}", ""]
    if e is not None and e.error:
        lines += [f"Trace failed: {e.error}", ""]
    if e is None or not e.buckets:
        return [*lines, "No funds to trace.", ""]
    lines += ["| Where | Category | Amount | Share | Hops | Source |", "|---|---|---|---|---|---|"]
    for b in e.buckets:
        if b.kind == "labeled":
            category = b.key
        elif b.kind == "own_cluster":
            category = f"{b.key} (own cluster)"
        else:
            category = b.kind.replace("_", " ")
        hops = "—" if b.min_hops is None else str(b.min_hops)
        lines.append(f"| {_cell(b.label)} | {category} | {btc(b.amount)} | {pct(b.share)} | {hops} | "
                     f"{_cell(b.source or '—')} |")
    if e.incomplete and e.reason and not e.error:
        lines += ["", f"Stopped early: {e.reason}"]
    return [*lines, ""]


def to_markdown(r: AnalysisReport) -> str:
    p, v, c = r.profile, r.verdict, r.cluster
    labels = ", ".join(f"{t['label']} ({t.get('abuse') or t['category']})" for t in p.info.get("tags", [])[:5])
    behaviour = ", ".join(f"{k} ×{n}" for k, n in p.behaviour.items())
    fp = p.fingerprint
    fingerprint = (f"{fp.signature} in {pct(fp.share)} of {fp.signed_txs} signed txs" if fp.signed_txs
                   else "no signed transactions")
    quiet = "—" if p.longest_gap_days is None else f"{p.longest_gap_days:g} days"
    lines = [
        f"# Address analysis: {r.address}", "",
        f"**Verdict: {v.level.upper()}**{' (low confidence: try a deeper analysis)' if v.low_confidence else ''}  ",
        f"{r.depth.capitalize()} analysis · {_date(r.generated_at)} · {r.calls_used} API calls  ",
        v.coverage, "",
        "## Why", "",
        *[f"- **{x.level}**: {x.text}" for x in v.reasons], "",
        "## Profile", "",
        "| | |", "|---|---|",
        f"| Address type | {p.address_type or 'unknown'}{' (reused)' if p.reused else ''} |",
        f"| Balance | {btc(p.stats.balance)} |",
        f"| Received / sent | {btc(p.stats.funded_sum)} / {btc(p.stats.spent_sum)} |",
        f"| Transactions | {p.stats.tx_count} ({p.txs_seen} analysed) |",
        f"| Active | {_date(p.first_seen)}{'' if p.history_complete else ' or earlier'} → {_date(p.last_seen)} |",
        f"| Longest quiet period | {quiet} |",
        f"| Labels | {_cell(labels or 'none')} |",
        f"| Behaviour | {_cell(behaviour or 'nothing notable')} |",
        f"| Wallet fingerprint | {_cell(fingerprint)} |", "",
        "## Cluster", "",
    ]
    if c is None:
        lines += ["Not expanded.", ""]
    else:
        lines.append(f"- Size: {c.size} addresses{' (partial)' if c.partial else ''}"
                     f"{'; capped, likely a large service' if c.capped else ''}")
        if c.top_labels:
            lines.append("- Labels: " + ", ".join(f"{t['label']} ×{t['count']}" for t in c.top_labels))
        if c.conflicts:
            lines.append("- Conflicting labels: " + "; ".join(" / ".join(x.labels) for x in c.conflicts))
        if c.error:
            lines.append(f"- Expansion failed: {c.error}")
        lines.append("")
    lines += _exposure_lines("Sources of funds", r.sources)
    lines += _exposure_lines("Destinations of funds", r.destinations)
    return "\n".join(lines).rstrip() + "\n"
