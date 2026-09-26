"""Convert Esplora (mempool.space / blockstream.info / electrs) JSON into chain models."""

from __future__ import annotations

from typing import Any

from btcintel.chain.models import AddressStats, Outspend, Tx, TxIn, TxOut, TxStatus


def _out(j: dict[str, Any], n: int) -> TxOut:
    return TxOut(
        n=n,
        value=j["value"],
        script_type=j.get("scriptpubkey_type", "unknown"),
        address=j.get("scriptpubkey_address"),
        script_hex=j.get("scriptpubkey", ""),
    )


def _status(j: dict[str, Any] | None) -> TxStatus:
    j = j or {}
    return TxStatus(
        confirmed=bool(j.get("confirmed")),
        block_height=j.get("block_height"),
        block_hash=j.get("block_hash"),
        block_time=j.get("block_time"),
    )


def parse_tx(j: dict[str, Any]) -> Tx:
    vin = []
    for i, v in enumerate(j["vin"]):
        prev = v.get("prevout")
        vin.append(
            TxIn(
                n=i,
                prev_txid=v["txid"],
                prev_vout=v["vout"],
                prevout=_out(prev, v["vout"]) if prev else None,
                is_coinbase=bool(v.get("is_coinbase", False)),
                sequence=v["sequence"],
                scriptsig_hex=v.get("scriptsig", "") or "",
                scriptsig_asm=v.get("scriptsig_asm", "") or "",
                witness=v.get("witness") or [],
                inner_redeemscript_asm=v.get("inner_redeemscript_asm"),
                inner_witnessscript_asm=v.get("inner_witnessscript_asm"),
            )
        )
    return Tx(
        txid=j["txid"],
        version=j["version"],
        locktime=j["locktime"],
        vin=vin,
        vout=[_out(o, n) for n, o in enumerate(j["vout"])],
        size=j["size"],
        weight=j["weight"],
        fee=j.get("fee", 0),
        status=_status(j.get("status")),
    )


def parse_outspends(j: list[dict[str, Any]]) -> list[Outspend]:
    return [
        Outspend(
            spent=bool(o.get("spent", False)),
            txid=o.get("txid"),
            vin=o.get("vin"),
            status=_status(o["status"]) if o.get("status") else None,
        )
        for o in j
    ]


def parse_address(j: dict[str, Any]) -> AddressStats:
    chain = j["chain_stats"]
    mem = j.get("mempool_stats") or {}
    return AddressStats(
        address=j["address"],
        tx_count=chain["tx_count"],
        funded_txo_count=chain["funded_txo_count"],
        funded_sum=chain["funded_txo_sum"],
        spent_txo_count=chain["spent_txo_count"],
        spent_sum=chain["spent_txo_sum"],
        mempool_tx_count=mem.get("tx_count", 0),
        mempool_delta=mem.get("funded_txo_sum", 0) - mem.get("spent_txo_sum", 0),
    )
