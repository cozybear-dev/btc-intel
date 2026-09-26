"""Synthetic transaction builders for unit tests (no network)."""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Sequence
from typing import Any

from btcintel.chain.models import Tx, TxIn, TxOut, TxStatus

_seq = itertools.count()


def fake_txid(tag: str | None = None) -> str:
    return hashlib.sha256((tag or f"tx-{next(_seq)}").encode()).hexdigest()


def op_return_script(payload: bytes) -> str:
    if len(payload) <= 75:
        return "6a" + f"{len(payload):02x}" + payload.hex()
    return "6a4c" + f"{len(payload):02x}" + payload.hex()


def mk_tx(
    inputs: Sequence[tuple[Any, ...]],
    outputs: Sequence[tuple[Any, ...]],
    *,
    txid: str | None = None,
    version: int = 2,
    locktime: int = 0,
    sequence: int = 0xFFFFFFFD,
    height: int | None = 800_000,
    confirmed: bool = True,
    coinbase: bool = False,
    witness: Sequence[Sequence[str]] | None = None,
    scriptsig_hex: str = "",
    op_returns: Sequence[bytes] = (),
    fee: int | None = None,
) -> Tx:
    """inputs: (address, value[, script_type]) or (parent_tx, vout); outputs: (address, value[, script_type])."""
    vin: list[TxIn] = []
    for i, spec in enumerate(inputs):
        if isinstance(spec[0], Tx):
            parent, vout = spec[0], spec[1]
            prev_txid, prev_vout, prevout = parent.txid, vout, parent.vout[vout]
        else:
            addr, value, *rest = spec
            st = rest[0] if rest else "v0_p2wpkh"
            prev_txid, prev_vout = fake_txid(), 0
            prevout = TxOut(n=0, value=value, address=addr, script_type=st)
        vin.append(
            TxIn(
                n=i,
                prev_txid="0" * 64 if coinbase else prev_txid,
                prev_vout=0xFFFFFFFF if coinbase else prev_vout,
                prevout=None if coinbase else prevout,
                is_coinbase=coinbase,
                sequence=sequence,
                scriptsig_hex=scriptsig_hex,
                witness=list(witness[i]) if witness else [],
            )
        )
    vout = [
        TxOut(n=n, value=value, address=addr, script_type=rest[0] if rest else "v0_p2wpkh")
        for n, (addr, value, *rest) in enumerate(outputs)
    ]
    for payload in op_returns:
        vout.append(TxOut(n=len(vout), value=0, script_type="op_return", script_hex=op_return_script(payload)))
    in_value = sum(i.value for i in vin)
    out_value = sum(o.value for o in vout)
    return Tx(
        txid=txid or fake_txid(),
        version=version,
        locktime=locktime,
        vin=vin,
        vout=vout,
        size=250,
        weight=1000,
        fee=fee if fee is not None else max(0, in_value - out_value),
        status=TxStatus(
            confirmed=confirmed,
            block_height=height if confirmed else None,
            block_time=1_700_000_000 if confirmed else None,
        ),
    )
