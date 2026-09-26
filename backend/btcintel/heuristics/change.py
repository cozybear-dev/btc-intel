"""H-CHG: change-output detection as a weighted log-odds vote over independent signals."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from btcintel.chain.models import Tx, TxOut
from btcintel.heuristics.base import Context, Finding, heuristic, out_subject
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, classify_coinjoin
from btcintel.heuristics.fingerprint import fingerprint

WEIGHTS = {
    "H-CHG-SELF": 4.0, "H-CHG-SCRIPT": 1.0, "H-CHG-ROUND": 1.2, "H-CHG-UNNECESSARY": 1.0,
    "H-CHG-FPCONT": 1.0,
}
MIN_PROBABILITY = 0.6
MAX_OUTPUTS = 4


@dataclass(frozen=True)
class Vote:
    signal: str
    output: int
    weight: float
    detail: str


@dataclass(frozen=True)
class ChangeResult:
    applicable: bool
    change_output: int | None
    probabilities: dict[int, float]
    votes: tuple[Vote, ...]
    reason: str = ""


def trailing_zeros(value: int) -> int:
    if value <= 0:
        return 0
    n = 0
    while value % 10 == 0:
        value //= 10
        n += 1
    return n


def applicability(tx: Tx) -> str | None:
    if tx.is_coinbase:
        return "coinbase"
    m = classify_coinjoin(tx)
    if m is not None and m.kind in MULTIPARTY_KINDS:
        return f"coinjoin:{m.kind}"
    outs = tx.spendable_outputs()
    if len(outs) < 2:
        return "fewer than two outputs"
    if len(outs) > MAX_OUTPUTS:
        return f"more than {MAX_OUTPUTS} outputs (batch payment)"
    return None


def offline_votes(tx: Tx) -> list[Vote]:
    outs = tx.spendable_outputs()
    votes: list[Vote] = []
    inputs = set(tx.input_addresses())
    for o in outs:
        if o.address and o.address in inputs:
            votes.append(Vote("H-CHG-SELF", o.n, WEIGHTS["H-CHG-SELF"], "pays back to an input address"))
    in_types = {i.script_type for i in tx.vin}
    if len(in_types) == 1:
        (itype,) = in_types
        same = [o for o in outs if o.script_type == itype]
        if len(same) == 1:
            w = WEIGHTS["H-CHG-SCRIPT"]
            votes.append(Vote("H-CHG-SCRIPT", same[0].n, w, f"only output with the inputs' script type {itype}"))
            votes += [Vote("H-CHG-SCRIPT", o.n, -0.5 * w, f"script type {o.script_type} differs from inputs")
                      for o in outs if o is not same[0]]
    round_outs = [o for o in outs if trailing_zeros(o.value) >= 5]
    ragged = [o for o in outs if trailing_zeros(o.value) <= 3]
    if len(ragged) == 1 and len(round_outs) == len(outs) - 1:
        w = WEIGHTS["H-CHG-ROUND"]
        votes.append(Vote("H-CHG-ROUND", ragged[0].n, w, "only non-round output"))
        votes += [Vote("H-CHG-ROUND", o.n, -w, f"round amount {o.value} sats looks like a payment")
                  for o in round_outs]
    if len(tx.vin) >= 2:
        smallest = min(i.value for i in tx.vin)
        below = [o for o in outs if o.value < smallest]
        if len(below) == 1:
            votes.append(Vote("H-CHG-UNNECESSARY", below[0].n, WEIGHTS["H-CHG-UNNECESSARY"],
                              f"smaller than the smallest input ({smallest} sats)"))
    return votes


async def fingerprint_votes(tx: Tx, ctx: Context) -> list[Vote]:
    spends = await ctx.outspends(tx.txid)
    if not spends:
        return []
    mine = fingerprint(tx).signature()
    w = WEIGHTS["H-CHG-FPCONT"]
    votes = []
    for o in tx.spendable_outputs():
        sp = spends[o.n] if o.n < len(spends) else None
        if sp is None or not sp.spent or not sp.txid:
            continue
        child = await ctx.tx(sp.txid)
        if child is None:
            continue
        if fingerprint(child).signature() == mine:
            votes.append(Vote("H-CHG-FPCONT", o.n, w, "spent by a transaction with the same wallet fingerprint"))
        else:
            votes.append(Vote("H-CHG-FPCONT", o.n, -0.3 * w,
                              "spent by a transaction with a different wallet fingerprint"))
    return votes


def combine(outputs: Sequence[TxOut], votes: Sequence[Vote]) -> tuple[int | None, dict[int, float]]:
    score = {o.n: 0.0 for o in outputs}
    for v in votes:
        score[v.output] += v.weight
    probs = {n: round(1 / (1 + math.exp(-s)), 4) for n, s in score.items()}
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    best, p = ranked[0]
    if p >= MIN_PROBABILITY and p > ranked[1][1]:
        return best, probs
    return None, probs


def _not_applicable(reason: str) -> ChangeResult:
    return ChangeResult(False, None, {}, (), reason)


def detect_change_offline(tx: Tx) -> ChangeResult:
    reason = applicability(tx)
    if reason:
        return _not_applicable(reason)
    votes = offline_votes(tx)
    change, probs = combine(tx.spendable_outputs(), votes)
    return ChangeResult(True, change, probs, tuple(votes))


async def detect_change(tx: Tx, ctx: Context | None = None) -> ChangeResult:
    reason = applicability(tx)
    if reason:
        return _not_applicable(reason)
    votes = offline_votes(tx)
    if ctx is not None and ctx.chain is not None:
        votes += await fingerprint_votes(tx, ctx)
    change, probs = combine(tx.spendable_outputs(), votes)
    return ChangeResult(True, change, probs, tuple(votes))


def remainder_output(tx: Tx) -> int | None:
    result = detect_change_offline(tx)
    if result.change_output is not None:
        return result.change_output
    outs = tx.spendable_outputs()
    return max(outs, key=lambda o: o.value).n if outs else None


@heuristic("H-CHG")
async def change_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    r = await detect_change(tx, ctx)
    if r.change_output is None:
        return []
    return [Finding(
        heuristic="H-CHG", subject=out_subject(tx.txid, r.change_output), label="change",
        confidence=r.probabilities[r.change_output],
        evidence={"votes": [asdict(v) for v in r.votes],
                  "probabilities": {str(k): v for k, v in r.probabilities.items()}},
    )]
