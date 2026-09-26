"""Compact, offline per-transaction labels for graph nodes and lists."""

from __future__ import annotations

from btcintel.chain.models import Tx
from btcintel.heuristics.coinjoin import classify_coinjoin
from btcintel.heuristics.crosschain import xchain_markers
from btcintel.heuristics.patterns import fanin_shape, fanout_shape, peel_shape


def tx_flags(tx: Tx) -> list[str]:
    flags = []
    if tx.is_coinbase:
        flags.append("coinbase")
    m = classify_coinjoin(tx)
    if m is not None:
        flags.append(f"coinjoin:{m.kind}")
    if peel_shape(tx):
        flags.append("peel_step")
    fanout = fanout_shape(tx)
    if fanout:
        flags.append(fanout["label"])
    if fanin_shape(tx):
        flags.append("consolidation")
    flags.extend(label for label, _, _ in xchain_markers(tx))
    return flags
