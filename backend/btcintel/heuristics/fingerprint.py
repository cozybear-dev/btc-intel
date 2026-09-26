"""H-FP: wallet fingerprinting from transaction fields and construction choices."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from btcintel.chain.models import Tx, TxIn
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject

LOCKTIME_THRESHOLD = 500_000_000
AFS_MAX_DELTA = 2016  # blocks between anti-fee-sniping locktime and inclusion height
FINAL_SEQUENCE = 0xFFFFFFFF
RBF_THRESHOLD = 0xFFFFFFFE  # BIP125: nSequence below this signals replaceability


@dataclass(frozen=True)
class Fingerprint:
    version: int
    locktime: int
    locktime_kind: str
    anti_fee_sniping: bool | None
    rbf: bool
    sequences: tuple[str, ...]
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    bip69: bool | None
    ecdsa_sigs: int
    high_r_sigs: int
    low_r_only: bool | None
    uncompressed_pubkey: bool
    has_op_return: bool
    feerate_int: bool | None

    def signature(self) -> str:
        """Wallet-choice traits used to compare two transactions (H-CHG-FPCONT)."""
        return "|".join([
            f"v{self.version}", f"lt:{self.locktime_kind}", f"rbf:{int(self.rbf)}",
            "in:" + ",".join(self.input_types),
        ])

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "signature": self.signature()}


def _asm_pushes(asm: str) -> list[bytes]:
    tokens = asm.split()
    out = []
    for i, tok in enumerate(tokens[:-1]):
        if tok.startswith("OP_PUSHBYTES_") or tok in ("OP_PUSHDATA1", "OP_PUSHDATA2", "OP_PUSHDATA4"):
            try:
                out.append(bytes.fromhex(tokens[i + 1]))
            except ValueError:
                continue
    return out


def _elements(txin: TxIn) -> list[bytes]:
    elems = []
    for w in txin.witness:
        try:
            elems.append(bytes.fromhex(w))
        except ValueError:
            continue
    return elems + _asm_pushes(txin.scriptsig_asm)


def _is_der_sig(b: bytes) -> bool:
    return len(b) >= 9 and b[0] == 0x30 and b[1] == len(b) - 3 and b[2] == 0x02


def _bip69(tx: Tx) -> bool | None:
    if len(tx.vin) < 2 and len(tx.vout) < 2:
        return None
    ins = [(i.prev_txid, i.prev_vout) for i in tx.vin]
    outs = [(o.value, bytes.fromhex(o.script_hex or "")) for o in tx.vout]
    return ins == sorted(ins) and outs == sorted(outs)


def fingerprint(tx: Tx) -> Fingerprint:
    if tx.locktime == 0:
        kind = "zero"
    elif tx.locktime < LOCKTIME_THRESHOLD:
        kind = "height"
    else:
        kind = "time"
    if not tx.status.confirmed or tx.status.block_height is None:
        afs: bool | None = None
    else:
        delta = tx.status.block_height - tx.locktime
        afs = kind == "height" and 1 <= delta <= AFS_MAX_DELTA
    ecdsa = high_r = 0
    uncompressed = False
    for txin in tx.vin:
        for el in _elements(txin):
            if _is_der_sig(el):
                ecdsa += 1
                high_r += el[3] == 33
            elif len(el) == 65 and el[0] == 0x04:
                uncompressed = True
    return Fingerprint(
        version=tx.version,
        locktime=tx.locktime,
        locktime_kind=kind,
        anti_fee_sniping=afs,
        rbf=any(i.sequence < RBF_THRESHOLD for i in tx.vin),
        sequences=tuple(sorted({f"{i.sequence:08x}" for i in tx.vin})),
        input_types=tuple(sorted({i.script_type or "unknown" for i in tx.vin})),
        output_types=tuple(sorted({o.script_type for o in tx.vout})),
        bip69=_bip69(tx),
        ecdsa_sigs=ecdsa,
        high_r_sigs=high_r,
        low_r_only=(high_r == 0) if ecdsa else None,
        uncompressed_pubkey=uncompressed,
        has_op_return=any(o.script_type == "op_return" for o in tx.vout),
        feerate_int=None if tx.is_coinbase or not tx.vsize else tx.fee % tx.vsize == 0,
    )


@heuristic("H-FP")
async def fingerprint_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    if tx.is_coinbase:
        return []
    return [Finding(heuristic="H-FP", subject=tx_subject(tx.txid), label="fingerprint",
                    confidence=1.0, evidence=fingerprint(tx).as_dict())]
