"""Chain lookups: search, transactions (with findings), addresses."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from btcintel import __version__
from btcintel.api.deps import rt, valid_address, valid_txid
from btcintel.chain.budget import CallBudget, budget_scope
from btcintel.chain.models import Tx
from btcintel.chain.validate import classify_query
from btcintel.heuristics.base import analyze_tx
from btcintel.heuristics.flags import tx_flags
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


def tx_summary(tx: Tx, address: str | None = None) -> dict[str, Any]:
    delta = None
    if address is not None:
        delta = (sum(o.value for o in tx.vout if o.address == address)
                 - sum(i.value for i in tx.vin if i.address == address))
    return {"txid": tx.txid, "block_height": tx.status.block_height, "block_time": tx.status.block_time,
            "fee": tx.fee, "n_in": len(tx.vin), "n_out": len(tx.vout), "value_out": tx.output_value,
            "delta": delta, "flags": tx_flags(tx)}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/search")
async def search(q: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    kind, value = classify_query(q)
    if kind == "text":
        return {"kind": kind, "query": value, "tags": [t.model_dump() for t in s.tags.search(value)]}
    return {"kind": kind, "query": value}


@router.get("/tx/{txid}")
async def get_tx(txid: str, price: bool = False, s: AppState = Depends(rt)) -> dict[str, Any]:
    tx = await s.chain.get_tx(valid_txid(txid))
    with budget_scope(CallBudget(40)):
        findings = await analyze_tx(tx, s.context())
    labels = s.labels()
    addresses = dict.fromkeys([*tx.input_addresses(), *tx.output_addresses()])
    price_usd = None
    if price and tx.status.block_time:
        price_usd = await s.chain.get_price_usd(tx.status.block_time)
    return {"tx": tx.model_dump(), "findings": [f.model_dump() for f in findings], "flags": tx_flags(tx),
            "addresses": {a: labels.lookup(a).to_dict() for a in addresses}, "price_usd": price_usd}


@router.get("/tx/{txid}/outspends")
async def get_outspends(txid: str, s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [o.model_dump() for o in await s.chain.get_outspends(valid_txid(txid))]


@router.get("/address/{address}")
async def get_address(address: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    stats = await s.chain.get_address(address)
    info = s.labels().lookup(address)
    meta = s.uf.meta(info.cluster) if info.cluster else None
    return {"stats": stats.model_dump(), "info": info.to_dict(),
            "cluster": meta.model_dump() if meta else None}


@router.get("/address/{address}/txs")
async def get_address_txs(address: str, after: str | None = None, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    page = await s.chain.get_address_txs(address, valid_txid(after) if after is not None else None)
    confirmed = [t for t in page if t.status.confirmed]
    return {"txs": [tx_summary(t, address) for t in page], "next": confirmed[-1].txid if confirmed else None}
