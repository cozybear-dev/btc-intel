"""ChainSource over one or more Esplora backends with caching and failover."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, TypeVar

from btcintel.chain.cache import Cache
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.esplora_parse import parse_address, parse_outspends, parse_tx
from btcintel.chain.models import AddressStats, Outspend, Tx

T = TypeVar("T")

IMMUTABLE_CONFIRMATIONS = 6
SHALLOW_TX_TTL = 60.0
VOLATILE_TTL = 120.0


class ChainClient:
    def __init__(self, backends: Sequence[EsploraBackend], cache: Cache, *, tip_ttl: float = 30.0) -> None:
        if not backends:
            raise ValueError("at least one backend is required")
        self.backends = list(backends)
        self.cache = cache
        self.tip_ttl = tip_ttl

    def _ordered(self, need_price: bool) -> list[EsploraBackend]:
        candidates = [b for b in self.backends if b.supports_price or not need_price]
        return sorted(candidates, key=lambda b: b.bucket.next_available())  # stable: config order on ties

    async def _call(self, fn: Callable[[EsploraBackend], Awaitable[T]], *, need_price: bool = False) -> T:
        candidates = self._ordered(need_price)
        if not candidates:
            raise SourceError("no configured backend supports this request")
        errors = []
        for backend in candidates:
            try:
                return await fn(backend)
            except SourceError as e:
                errors.append(str(e))
        raise SourceError("all backends failed: " + "; ".join(errors))

    async def tip_height(self) -> int:
        cached = self.cache.get_json("tip")
        if cached is not None:
            return int(cached)
        height = int((await self._call(lambda b: b.get_text("/blocks/tip/height"))).strip())
        self.cache.put_json("tip", height, self.tip_ttl)
        return height

    async def _deep(self, height: int | None) -> bool:
        if height is None:
            return False
        return (await self.tip_height()) - height + 1 >= IMMUTABLE_CONFIRMATIONS

    async def _store_tx(self, raw: dict[str, Any]) -> None:
        status = raw.get("status") or {}
        deep = bool(status.get("confirmed")) and await self._deep(status.get("block_height"))
        self.cache.put_json(f"tx:{raw['txid']}", raw, None if deep else SHALLOW_TX_TTL)

    async def get_tx(self, txid: str) -> Tx:
        raw = self.cache.get_json(f"tx:{txid}")
        if raw is None:
            raw = await self._call(lambda b: b.get_json(f"/tx/{txid}"))
            await self._store_tx(raw)
        return parse_tx(raw)

    async def get_outspends(self, txid: str) -> list[Outspend]:
        key = f"outspends:{txid}"
        raw = self.cache.get_json(key)
        if raw is not None:
            return parse_outspends(raw)
        raw = await self._call(lambda b: b.get_json(f"/tx/{txid}/outspends"))
        spends = parse_outspends(raw)
        immutable = bool(spends)
        for o in spends:
            if not (o.spent and o.status and o.status.confirmed and await self._deep(o.status.block_height)):
                immutable = False
                break
        self.cache.put_json(key, raw, None if immutable else VOLATILE_TTL)
        return spends

    async def get_address(self, address: str) -> AddressStats:
        key = f"addr:{address}"
        raw = self.cache.get_json(key)
        if raw is None:
            raw = await self._call(lambda b: b.get_json(f"/address/{address}"))
            self.cache.put_json(key, raw, VOLATILE_TTL)
        return parse_address(raw)

    async def get_address_txs(self, address: str, after_txid: str | None = None) -> list[Tx]:
        path = f"/address/{address}/txs" + (f"/chain/{after_txid}" if after_txid else "")
        key = f"addrtxs:{address}:{after_txid or ''}"
        raw = self.cache.get_json(key)
        if raw is None:
            raw = await self._call(lambda b: b.get_json(path))
            self.cache.put_json(key, raw, VOLATILE_TTL)
            for tx_raw in raw:
                await self._store_tx(tx_raw)
        return [parse_tx(t) for t in raw]

    async def iter_address_txs(self, address: str, max_txs: int = 1000) -> AsyncIterator[Tx]:
        seen: set[str] = set()
        after: str | None = None
        while len(seen) < max_txs:
            page = await self.get_address_txs(address, after)
            fresh = [t for t in page if t.txid not in seen]
            if not fresh:
                return
            for tx in fresh:
                seen.add(tx.txid)
                yield tx
                if len(seen) >= max_txs:
                    return
            confirmed = [t for t in page if t.status.confirmed]
            if not confirmed:
                return
            after = confirmed[-1].txid

    async def get_price_usd(self, ts: int) -> float | None:
        hour = ts - ts % 3600
        key = f"price:USD:{hour}"
        cached = self.cache.get_json(key)
        if cached is not None:
            return float(cached)
        try:
            raw = await self._call(
                lambda b: b.get_json(f"/v1/historical-price?currency=USD&timestamp={hour}"),
                need_price=True,
            )
        except (NotFound, SourceError):
            return None
        prices = raw.get("prices") or []
        if not prices or "USD" not in prices[0]:
            return None
        usd = float(prices[0]["USD"])
        self.cache.put_json(key, usd, None)
        return usd
