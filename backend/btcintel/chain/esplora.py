"""One Esplora-compatible HTTP backend (mempool.space, blockstream.info, self-hosted)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from btcintel.chain.budget import charge_budget
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.ratelimit import TokenBucket
from btcintel.config import BackendConfig


def _backoff(attempt: int) -> float:
    return min(30.0, 0.5 * 2**attempt)


def _retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None  # HTTP-date form: fall back to exponential backoff


class EsploraBackend:
    def __init__(
        self,
        cfg: BackendConfig,
        client: httpx.AsyncClient,
        *,
        bucket: TokenBucket | None = None,
        max_retries: int = 4,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.cfg = cfg
        self.name = cfg.name
        self.supports_price = cfg.supports_price
        self.client = client
        self.bucket = bucket or TokenBucket(cfg.rate_per_sec, cfg.burst)
        self.max_retries = max_retries
        self._sleep = sleep

    async def get_json(self, path: str) -> Any:
        return (await self._request(path)).json()

    async def get_text(self, path: str) -> str:
        return (await self._request(path)).text

    async def _request(self, path: str) -> httpx.Response:
        url = self.cfg.base_url + path
        last = "no attempt made"
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            await self.bucket.acquire()
            charge_budget()
            try:
                resp = await self.client.get(url, headers=dict(self.cfg.headers))
            except httpx.TransportError as e:
                last = f"{type(e).__name__}: {e}"
                await self._sleep(_backoff(attempt))
                continue
            status = resp.status_code
            if status == 200:
                return resp
            if status in (400, 404):
                raise NotFound(f"{self.name}: {path} (HTTP {status})")
            if status == 429:
                self.bucket.penalize(_retry_after(resp.headers.get("Retry-After")) or _backoff(attempt))
                last = "HTTP 429"
                continue
            if status >= 500:
                last = f"HTTP {status}"
                await self._sleep(_backoff(attempt))
                continue
            raise SourceError(f"{self.name}: {path} HTTP {status}")
        raise SourceError(f"{self.name}: {path} failed after {attempts} attempts ({last})")
