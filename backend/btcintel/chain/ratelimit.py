"""Async token bucket used to respect public API rate limits."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class TokenBucket:
    def __init__(
        self,
        rate: float,
        burst: int = 1,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate <= 0 or burst < 1:
            raise ValueError("rate must be > 0 and burst >= 1")
        self.rate = rate
        self.burst = burst
        self._clock = clock
        self._sleep = sleep
        self._tokens = float(burst)
        self._last = clock()
        self._blocked_until = 0.0
        self._lock = asyncio.Lock()

    def _refill(self, now: float) -> None:
        self._tokens = min(float(self.burst), self._tokens + (now - self._last) * self.rate)
        self._last = now

    def next_available(self) -> float:
        now = self._clock()
        self._refill(now)
        token_wait = 0.0 if self._tokens >= 1 else (1 - self._tokens) / self.rate
        return max(token_wait, self._blocked_until - now, 0.0)

    def penalize(self, seconds: float) -> None:
        self._blocked_until = max(self._blocked_until, self._clock() + seconds)

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._clock()
                self._refill(now)
                if now < self._blocked_until:
                    await self._sleep(self._blocked_until - now)
                    continue
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await self._sleep((1 - self._tokens) / self.rate)
