"""Follow a peel chain: repeatedly take the remainder output and record the peeled payments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from btcintel.chain.budget import BudgetExceeded
from btcintel.chain.source import ChainSource
from btcintel.heuristics.change import remainder_output
from btcintel.heuristics.coinjoin import is_multiparty
from btcintel.heuristics.patterns import peel_shape
from btcintel.labels.lookup import LabelLookup


class PeelStep(BaseModel):
    txid: str
    remainder_vout: int
    remainder_value: int
    peels: list[dict[str, Any]]


class PeelChain(BaseModel):
    start_txid: str
    steps: list[PeelStep]
    end_reason: Literal["unspent", "not_peel_shaped", "max_steps", "labeled", "coinjoin", "budget"]
    end_txid: str | None = None
    total_peeled: int


async def follow_peel_chain(start_txid: str, chain: ChainSource, labels: LabelLookup,
                            max_steps: int = 50) -> PeelChain:
    steps: list[PeelStep] = []

    def done(reason: str, end: str | None) -> PeelChain:
        return PeelChain(start_txid=start_txid, steps=steps, end_reason=reason, end_txid=end,  # type: ignore[arg-type]
                         total_peeled=sum(p["value"] for s in steps for p in s.peels))

    txid = start_txid
    try:
        for _ in range(max_steps):
            tx = await chain.get_tx(txid)
            if is_multiparty(tx):
                return done("coinjoin", txid)
            keep = remainder_output(tx) if peel_shape(tx) else None
            if keep is None:
                return done("not_peel_shaped", txid)
            peels = [{"vout": o.n, "address": o.address, "value": o.value,
                      "label": labels.lookup(o.address).label if o.address else None}
                     for o in tx.spendable_outputs() if o.n != keep]
            steps.append(PeelStep(txid=tx.txid, remainder_vout=keep, remainder_value=tx.vout[keep].value,
                                  peels=peels))
            rem = tx.vout[keep]
            if rem.address and labels.lookup(rem.address).stop_category:
                return done("labeled", tx.txid)
            spends = await chain.get_outspends(tx.txid)
            sp = spends[keep] if keep < len(spends) else None
            if sp is None or not sp.spent or not sp.txid:
                return done("unspent", tx.txid)
            txid = sp.txid
    except BudgetExceeded:
        return done("budget", txid)
    return done("max_steps", txid)
