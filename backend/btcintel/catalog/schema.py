"""Pydantic models for the machine-readable knowledge-base catalog (catalog/*.yaml)."""

from __future__ import annotations

from functools import cached_property
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RiskLevel = Literal["none", "low", "medium", "high", "severe"]
RISK_ORDER: dict[str, int] = {"none": 0, "low": 1, "medium": 2, "high": 3, "severe": 4}

Tactic = Literal["acquisition", "layering", "obfuscation", "chain_hopping", "offchain", "integration"]
FatfSection = Literal[
    "transactions", "transaction_patterns", "anonymity", "senders_recipients",
    "source_of_funds", "geographical",
]


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Reference(_Entry):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    title: str
    authors: list[str] = []
    year: int
    kind: Literal["paper", "court", "government", "industry", "docs", "news", "dataset", "code"]
    url: str = Field(pattern=r"^https?://")
    venue: str | None = None
    note: str | None = None


class Category(_Entry):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    kind: Literal["entity", "abuse"]
    name: str
    risk: RiskLevel
    gs_concepts: list[str] = []
    stop_trace: bool = False
    description: str


class Heuristic(_Entry):
    id: str = Field(pattern=r"^H-[A-Z0-9-]+$")
    name: str
    family: Literal[
        "clustering", "change", "fingerprint", "coinjoin", "pattern", "crosschain",
        "attribution", "taint", "temporal", "network",
    ]
    status: Literal["implemented", "planned", "kb_only"]
    implemented_by: str | None = None
    parent: str | None = None
    confidence: Literal["high", "medium", "low"]
    summary: str
    signals: list[str]
    false_positives: list[str] = []
    refs: list[str]
    kb: str

    @model_validator(mode="after")
    def _implemented_needs_target(self) -> Heuristic:
        if (self.status == "implemented") != (self.implemented_by is not None):
            raise ValueError("status 'implemented' requires implemented_by (and only then)")
        return self


class Technique(_Entry):
    id: str = Field(pattern=r"^O-[A-Z0-9-]+$")
    name: str
    tactic: Tactic
    summary: str
    examples: list[str] = []
    evades: list[str] = []
    detected_by: list[str] = []
    oak: list[str] = []
    fatf: list[FatfSection] = []
    refs: list[str]
    kb: str

    @model_validator(mode="after")
    def _oak_format(self) -> Technique:
        import re

        bad = [o for o in self.oak if not re.fullmatch(r"OAK-T\d+\.\d{3}", o)]
        if bad:
            raise ValueError(f"malformed OAK ids: {bad}")
        return self


class Seed(_Entry):
    kind: Literal["address", "tx"]
    value: str
    role: Literal["victim", "theft", "laundering", "exit", "seizure", "ransom", "other"]
    ref: str
    note: str | None = None


class Incident(_Entry):
    id: str = Field(pattern=r"^I-\d{4}-[A-Z0-9-]+$")
    name: str
    date: str = Field(pattern=r"^\d{4}(-\d{2}(-\d{2})?)?$")
    loss: str
    btc: float | None = None
    vector: list[str]
    actor: str | None = None
    attribution: Literal["confirmed", "suspected", "unknown"]
    techniques: list[str]
    summary: str
    seeds: list[Seed] = []
    seeds_note: str | None = None
    refs: list[str]
    kb: str

    @model_validator(mode="after")
    def _seeds_or_note(self) -> Incident:
        if not self.seeds and not self.seeds_note:
            raise ValueError("incident needs at least one seed or a seeds_note explaining why none")
        return self


class Catalog(_Entry):
    model_config = ConfigDict(extra="forbid", frozen=True, ignored_types=(cached_property,))

    references: list[Reference]
    categories: list[Category]
    heuristics: list[Heuristic]
    techniques: list[Technique]
    incidents: list[Incident]

    @cached_property
    def lookup(self) -> dict[str, dict[str, BaseModel]]:
        return {
            "reference": {r.id: r for r in self.references},
            "category": {c.id: c for c in self.categories},
            "heuristic": {h.id: h for h in self.heuristics},
            "technique": {t.id: t for t in self.techniques},
            "incident": {i.id: i for i in self.incidents},
        }

    def reference(self, rid: str) -> Reference:
        return self.lookup["reference"][rid]  # type: ignore[return-value]

    def category(self, cid: str) -> Category:
        return self.lookup["category"][cid]  # type: ignore[return-value]

    def heuristic(self, hid: str) -> Heuristic:
        return self.lookup["heuristic"][hid]  # type: ignore[return-value]

    def technique(self, tid: str) -> Technique:
        return self.lookup["technique"][tid]  # type: ignore[return-value]
