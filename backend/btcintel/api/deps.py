"""Request-scoped helpers: runtime access and identifier validation."""

from __future__ import annotations

from fastapi import HTTPException, Request

from btcintel.chain.validate import is_address, is_txid, normalize_address
from btcintel.runtime import AppState


def rt(request: Request) -> AppState:
    return request.app.state.rt


def valid_txid(txid: str) -> str:
    if not is_txid(txid):
        raise HTTPException(status_code=400, detail="invalid txid")
    return txid.lower()


def valid_address(address: str) -> str:
    if not is_address(address):
        raise HTTPException(status_code=400, detail="invalid Bitcoin mainnet address")
    return normalize_address(address)
