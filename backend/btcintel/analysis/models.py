"""Data model of an automatic address analysis (profile, cluster, exposure, verdict, report)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from btcintel.catalog.schema import RiskLevel
from btcintel.chain.models import AddressStats
from btcintel.cluster.expand import Conflict

Depth = Literal["quick", "deep"]
Direction = Literal["backward", "forward"]
BucketKind = Literal[
    "labeled", "own_cluster", "coinjoin", "unspent", "coinbase", "limits", "remainder"
]


class AnalysisPolicy(BaseModel):
    depth: Depth
    history_txs: int
    trace_hops: int
    trace_txs: int
    trace_calls: int
    cluster_addresses: int
    cluster_calls: int
    min_value_sats: int = 10_000

    @classmethod
    def quick(cls) -> AnalysisPolicy:
        """At most about 300 API calls: usually under a minute on the public Esplora APIs."""
        return cls(
            depth="quick",
            history_txs=100,
            trace_hops=3,
            trace_txs=60,
            trace_calls=120,
            cluster_addresses=200,
            cluster_calls=60,
        )

    @classmethod
    def deep(cls) -> AnalysisPolicy:
        """About 1,600+ API calls: 5-10 min on the public Esplora APIs."""
        return cls(
            depth="deep",
            history_txs=500,
            trace_hops=6,
            trace_txs=300,
            trace_calls=600,
            cluster_addresses=2000,
            cluster_calls=400,
        )


class FingerprintSummary(BaseModel):
    signed_txs: int
    signature: str | None = None
    share: float = 0.0  # share of signed txs carrying the dominant signature
    traits: dict[str, Any] = {}


class Profile(BaseModel):
    address: str
    address_type: str | None
    stats: AddressStats
    info: dict[str, Any]  # AddressInfo.to_dict(): own + cluster-inherited tags, risk
    txs_seen: int
    history_complete: bool
    first_seen: int | None
    last_seen: int | None
    longest_gap_days: float | None
    received_txs: int
    sent_txs: int
    received_external: int  # received in txs the address did not fund itself: traced total
    reused: bool
    behaviour: dict[str, int]  # tx flag -> count over the analysed history
    fingerprint: FingerprintSummary


class ClusterSummary(BaseModel):
    root: str
    size: int
    partial: bool
    capped: bool
    conflicts: list[Conflict] = []
    top_labels: list[dict[str, Any]] = []
    calls_used: int = 0
    error: str | None = None


class Bucket(BaseModel):
    kind: BucketKind
    key: str  # category/abuse id, coinjoin kind, or the stop reason
    label: str
    risk: RiskLevel = "none"
    source: str | None = None  # tag pack of the label
    amount: float = 0.0  # sats
    share: float = 0.0
    min_hops: int | None = None
    nodes: list[str] = []  # graph node ids of example endpoints


class Exposure(BaseModel):
    direction: Direction
    total: float
    buckets: list[Bucket]
    resolved_share: float
    incomplete: bool = False
    reason: str | None = None
    calls_used: int = 0
    error: str | None = None


class Reason(BaseModel):
    level: RiskLevel
    rule: str
    text: str


class Verdict(BaseModel):
    level: RiskLevel
    final: bool
    low_confidence: bool = False
    coverage: str
    reasons: list[Reason]


class AnalysisReport(BaseModel):
    address: str
    depth: Depth
    generated_at: float
    profile: Profile
    cluster: ClusterSummary | None
    sources: Exposure | None
    destinations: Exposure | None
    verdict: Verdict
    calls_used: int
    markdown: str = ""
