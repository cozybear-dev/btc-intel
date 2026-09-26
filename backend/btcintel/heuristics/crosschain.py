"""H-XCHAIN: cross-chain exit markers in OP_RETURN data (THORChain memos, Omni Layer)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject
from btcintel.heuristics.script import is_printable_ascii, op_return_payloads

_SWAP = {"SWAP", "S", "=", "=<"}
_ADD = {"ADD", "A", "+"}
_WITHDRAW = {"WITHDRAW", "WD", "-"}
_DONATE = {"DONATE", "D"}
_ASSET = re.compile(r"^[A-Za-z0-9]+[.~/][A-Za-z0-9._\-]+$")
_HASH = re.compile(r"^[0-9A-Fa-f]{64}$")


@dataclass(frozen=True)
class ThorMemo:
    action: str
    asset: str | None
    destination: str | None
    inbound_hash: str | None
    memo: str


def parse_thorchain_memo(text: str) -> ThorMemo | None:
    memo = text.strip()
    parts = memo.split(":")
    fn = parts[0].upper()

    def arg(k: int) -> str | None:
        return parts[k].strip() if len(parts) > k and parts[k].strip() else None

    if fn in ("OUT", "REFUND"):
        h = arg(1)
        if h is None or not _HASH.match(h):
            return None
        return ThorMemo("outbound" if fn == "OUT" else "refund", None, None, h, memo)
    asset = arg(1)
    if asset is None or not _ASSET.match(asset):
        return None
    if fn in _SWAP:
        return ThorMemo("swap", asset.upper(), arg(2), None, memo)
    if fn in _ADD:
        return ThorMemo("add", asset.upper(), arg(2), None, memo)
    if fn in _WITHDRAW:
        return ThorMemo("withdraw", asset.upper(), None, None, memo)
    if fn in _DONATE:
        return ThorMemo("donate", asset.upper(), None, None, memo)
    return None


def xchain_markers(tx: Tx) -> list[tuple[str, float, dict[str, Any]]]:
    markers = []
    for payload in op_return_payloads(tx):
        if payload.startswith(b"omni"):
            markers.append(("omni_layer", 0.95, {"payload_hex": payload.hex()}))
            continue
        if not is_printable_ascii(payload):
            continue
        memo = parse_thorchain_memo(payload.decode("ascii"))
        if memo is not None:
            markers.append((f"thorchain:{memo.action}", 0.9, asdict(memo)))
    return markers


@heuristic("H-XCHAIN")
async def crosschain_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    return [Finding(heuristic="H-XCHAIN", subject=tx_subject(tx.txid), label=label,
                    confidence=confidence, evidence=evidence)
            for label, confidence, evidence in xchain_markers(tx)]
