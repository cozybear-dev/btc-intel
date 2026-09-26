"""H-CIOH: common-input-ownership, suppressed for multi-party (CoinJoin/Stonewall) transactions."""

from __future__ import annotations

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, classify_coinjoin


def cioh_addresses(tx: Tx) -> list[str] | None:
    if tx.is_coinbase:
        return None
    m = classify_coinjoin(tx)
    if m is not None and m.kind in MULTIPARTY_KINDS:
        return None
    addresses = tx.input_addresses()
    return addresses if len(addresses) >= 2 else None


@heuristic("H-CIOH")
async def cioh_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    if tx.is_coinbase:
        return []
    addresses = tx.input_addresses()
    if len(addresses) < 2:
        return []
    m = classify_coinjoin(tx)
    if m is not None and m.kind in MULTIPARTY_KINDS:
        return [Finding(heuristic="H-CIOH", subject=tx_subject(tx.txid), label="cioh_suppressed",
                        confidence=1.0,
                        evidence={"reason": f"coinjoin:{m.kind}", "input_addresses": len(addresses)})]
    return [Finding(heuristic="H-CIOH", subject=tx_subject(tx.txid), label="common_input",
                    confidence=0.95, evidence={"addresses": addresses})]
