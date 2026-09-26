"""Heuristic framework: findings, analysis context, and the detector registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from btcintel.chain.errors import ChainError
from btcintel.chain.models import Outspend, Tx
from btcintel.chain.source import ChainSource


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    heuristic: str
    subject: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)


def tx_subject(txid: str) -> str:
    return f"tx:{txid}"


def out_subject(txid: str, n: int) -> str:
    return f"out:{txid}:{n}"


@dataclass
class Context:
    """What a detector may use beyond the transaction itself. No chain = offline analysis."""

    chain: ChainSource | None = None
    coinbase_rules: list[tuple[str, str]] = field(default_factory=list)

    async def outspends(self, txid: str) -> list[Outspend] | None:
        return await self.chain.get_outspends(txid) if self.chain else None

    async def tx(self, txid: str) -> Tx | None:
        return await self.chain.get_tx(txid) if self.chain else None


HeuristicFn = Callable[[Tx, Context], Awaitable[list[Finding]]]
_REGISTRY: dict[str, HeuristicFn] = {}


def heuristic(hid: str) -> Callable[[HeuristicFn], HeuristicFn]:
    def register(fn: HeuristicFn) -> HeuristicFn:
        if hid in _REGISTRY and _REGISTRY[hid] is not fn:
            raise ValueError(f"duplicate heuristic id {hid}")
        _REGISTRY[hid] = fn
        return fn

    return register


def registry() -> dict[str, HeuristicFn]:
    import btcintel.heuristics.all  # noqa: F401  (registers every detector)

    return dict(_REGISTRY)


async def analyze_tx(
    tx: Tx,
    ctx: Context,
    only: Iterable[str] | None = None,
    heuristics: Mapping[str, HeuristicFn] | None = None,
) -> list[Finding]:
    detectors = heuristics if heuristics is not None else registry()
    wanted = set(only) if only is not None else None
    findings: list[Finding] = []
    for hid, fn in detectors.items():
        if wanted is not None and hid not in wanted:
            continue
        try:
            findings.extend(await fn(tx, ctx))
        except ChainError as e:
            findings.append(Finding(heuristic=hid, subject=tx_subject(tx.txid), label="incomplete",
                                    confidence=0.0, evidence={"error": str(e)}))
    return findings
