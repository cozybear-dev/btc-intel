"""H-PEEL, H-MOTIF-FANOUT, H-MOTIF-FANIN: structural motifs of a single transaction."""

from __future__ import annotations

import statistics
from typing import Any

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject
from btcintel.heuristics.coinjoin import is_multiparty

PEEL_REMAINDER_SHARE = 0.75
FANOUT_MIN_OUTPUTS = 10
FANOUT_MAX_INPUTS = 3
UNIFORM_CV = 0.2
FANIN_MIN_INPUTS = 10
FANIN_MAX_OUTPUTS = 2


def peel_shape(tx: Tx) -> dict[str, Any] | None:
    outs = tx.spendable_outputs()
    if tx.is_coinbase or not 1 <= len(tx.vin) <= 2 or len(outs) != 2:
        return None
    total = sum(o.value for o in outs)
    big, small = sorted(outs, key=lambda o: o.value, reverse=True)
    if total <= 0 or big.value < PEEL_REMAINDER_SHARE * total:
        return None
    return {"remainder_output": big.n, "peel_output": small.n, "peel_value": small.value,
            "remainder_share": round(big.value / total, 3)}


def fanout_shape(tx: Tx) -> dict[str, Any] | None:
    outs = tx.spendable_outputs()
    if tx.is_coinbase or len(outs) < FANOUT_MIN_OUTPUTS or len(tx.vin) > FANOUT_MAX_INPUTS:
        return None
    if is_multiparty(tx):
        return None
    values = [o.value for o in outs]
    mean = statistics.fmean(values)
    cv = statistics.pstdev(values) / mean if mean else 0.0
    return {"label": "dispersal_uniform" if cv < UNIFORM_CV else "fan_out", "n_out": len(outs),
            "cv": round(cv, 3)}


def fanin_shape(tx: Tx) -> dict[str, Any] | None:
    if tx.is_coinbase or len(tx.vin) < FANIN_MIN_INPUTS:
        return None
    if len(tx.spendable_outputs()) > FANIN_MAX_OUTPUTS or is_multiparty(tx):
        return None
    return {"n_in": len(tx.vin), "distinct_input_addresses": len(tx.input_addresses())}


@heuristic("H-PEEL")
async def peel_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    shape = peel_shape(tx)
    if shape is None:
        return []
    return [Finding(heuristic="H-PEEL", subject=tx_subject(tx.txid), label="peel_step",
                    confidence=0.5, evidence=shape)]


@heuristic("H-MOTIF-FANOUT")
async def fanout_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    shape = fanout_shape(tx)
    if shape is None:
        return []
    confidence = 0.6 if shape["label"] == "dispersal_uniform" else 0.5
    return [Finding(heuristic="H-MOTIF-FANOUT", subject=tx_subject(tx.txid), label=shape["label"],
                    confidence=confidence, evidence=shape)]


@heuristic("H-MOTIF-FANIN")
async def fanin_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    shape = fanin_shape(tx)
    if shape is None:
        return []
    return [Finding(heuristic="H-MOTIF-FANIN", subject=tx_subject(tx.txid), label="consolidation",
                    confidence=0.6, evidence=shape)]
