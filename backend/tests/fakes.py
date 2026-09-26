"""Test doubles shared across the test suite."""

from __future__ import annotations


class FakeTime:
    """Deterministic clock + sleep: sleeping advances the clock instantly."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(round(seconds, 6))
        self.now += seconds
from collections.abc import AsyncIterator, Iterable  # noqa: E402

from btcintel.chain.budget import charge_budget  # noqa: E402
from btcintel.chain.errors import NotFound, SourceError  # noqa: E402
from btcintel.chain.models import AddressStats, Outspend, Tx, TxStatus  # noqa: E402


class FakeChain:
    """In-memory ChainSource. Outspends and address histories are derived from held txs."""

    def __init__(self, txs: Iterable[Tx] = (), tip: int = 900_000, fail_on: Iterable[str] = ()) -> None:
        self.txs: dict[str, Tx] = {}
        self.tip = tip
        self.fail_on = set(fail_on)
        self.calls = 0
        self.add(*txs)

    def add(self, *txs: Tx) -> None:
        for tx in txs:
            self.txs[tx.txid] = tx

    def _charge(self, txid: str | None = None) -> None:
        self.calls += 1
        charge_budget()
        if txid is not None and txid in self.fail_on:
            raise SourceError(f"fake backend failure for {txid}")

    def _history(self, address: str) -> list[Tx]:
        return [
            t for t in self.txs.values()
            if address in t.input_addresses() or address in t.output_addresses()
        ]

    async def get_tx(self, txid: str) -> Tx:
        self._charge(txid)
        if txid not in self.txs:
            raise NotFound(txid)
        return self.txs[txid]

    async def get_outspends(self, txid: str) -> list[Outspend]:
        self._charge(txid)
        tx = self.txs.get(txid)
        if tx is None:
            raise NotFound(txid)
        spends = [Outspend(spent=False) for _ in tx.vout]
        for child in self.txs.values():
            for i in child.vin:
                if i.prev_txid == txid and i.prev_vout < len(spends):
                    spends[i.prev_vout] = Outspend(
                        spent=True, txid=child.txid, vin=i.n,
                        status=TxStatus(confirmed=True, block_height=child.status.block_height),
                    )
        return spends

    async def get_address(self, address: str) -> AddressStats:
        self._charge()
        hist = self._history(address)
        funded = [o for t in hist for o in t.vout if o.address == address]
        spent = [i for t in hist for i in t.vin if i.address == address]
        return AddressStats(
            address=address, tx_count=len(hist), funded_txo_count=len(funded),
            funded_sum=sum(o.value for o in funded), spent_txo_count=len(spent),
            spent_sum=sum(i.value for i in spent),
        )

    async def get_address_txs(self, address: str, after_txid: str | None = None) -> list[Tx]:
        self._charge()
        hist = self._history(address)
        ids = [t.txid for t in hist]
        start = ids.index(after_txid) + 1 if after_txid in ids else 0
        return hist[start : start + 25]

    async def iter_address_txs(self, address: str, max_txs: int = 1000) -> AsyncIterator[Tx]:
        for i, tx in enumerate(self._history(address)[:max_txs]):
            if i % 25 == 0:
                self._charge()
            yield tx

    async def tip_height(self) -> int:
        self._charge()
        return self.tip

    async def get_price_usd(self, ts: int) -> float | None:
        return None
