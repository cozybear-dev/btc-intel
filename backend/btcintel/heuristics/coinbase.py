"""H-COINBASE: attribute newly mined coins to pools via coinbase scriptSig tags."""

from __future__ import annotations

from collections.abc import Sequence

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject


def _decode(scriptsig_hex: str) -> str:
    try:
        return bytes.fromhex(scriptsig_hex).decode("latin-1")
    except ValueError:
        return ""


def coinbase_text(tx: Tx) -> str:
    return "".join(ch for ch in _decode(tx.vin[0].scriptsig_hex) if 32 <= ord(ch) < 127)


def match_pool(scriptsig_hex: str, rules: Sequence[tuple[str, str]]) -> str | None:
    text = _decode(scriptsig_hex)
    for tag, pool in rules:
        if tag and tag in text:
            return pool
    return None


@heuristic("H-COINBASE")
async def coinbase_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    if not tx.is_coinbase:
        return []
    text = coinbase_text(tx)
    pool = match_pool(tx.vin[0].scriptsig_hex, ctx.coinbase_rules)
    if pool:
        return [Finding(heuristic="H-COINBASE", subject=tx_subject(tx.txid), label=f"miner:{pool}",
                        confidence=0.9, evidence={"pool": pool, "coinbase_text": text})]
    return [Finding(heuristic="H-COINBASE", subject=tx_subject(tx.txid), label="miner:unknown",
                    confidence=0.5, evidence={"coinbase_text": text})]
