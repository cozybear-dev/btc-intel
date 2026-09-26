"""The data-source interface every analysis component depends on."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from btcintel.chain.models import AddressStats, Outspend, Tx


class ChainSource(Protocol):
    async def get_tx(self, txid: str) -> Tx: ...

    async def get_outspends(self, txid: str) -> list[Outspend]: ...

    async def get_address(self, address: str) -> AddressStats: ...

    async def get_address_txs(self, address: str, after_txid: str | None = None) -> list[Tx]: ...

    def iter_address_txs(self, address: str, max_txs: int = 1000) -> AsyncIterator[Tx]: ...

    async def tip_height(self) -> int: ...

    async def get_price_usd(self, ts: int) -> float | None: ...
