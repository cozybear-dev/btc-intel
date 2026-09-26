"""Per-address attribution view: own tags, tags inherited from the address's cluster, risk, stops."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from btcintel.catalog.schema import RISK_ORDER
from btcintel.chain.validate import normalize_address
from btcintel.cluster.unionfind import UnionFind
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy


@dataclass(frozen=True)
class AddressInfo:
    address: str
    tags: tuple[Tag, ...]
    cluster: str | None
    category: str | None
    label: str | None
    risk: str
    stop_category: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address, "tags": [t.model_dump() for t in self.tags[:10]],
            "cluster": self.cluster, "category": self.category, "label": self.label,
            "risk": self.risk, "stop_category": self.stop_category,
        }


def _rank(t: Tag) -> tuple[int, str]:
    return (-t.confidence_level, t.label)


class LabelLookup:
    def __init__(self, tags: TagStore, taxonomy: Taxonomy, uf: UnionFind | None = None,
                 stop_categories: Iterable[str] | None = None, cluster_member_limit: int = 5000) -> None:
        self.tags = tags
        self.taxonomy = taxonomy
        self.uf = uf
        self.stop = set(stop_categories) if stop_categories is not None else taxonomy.default_stop_categories()
        self.cluster_member_limit = cluster_member_limit
        self._cache: dict[str, AddressInfo] = {}
        self._cluster_tags: dict[str, list[Tag]] = {}

    def lookup(self, address: str) -> AddressInfo:
        address = normalize_address(address)
        cached = self._cache.get(address)
        if cached is not None:
            return cached
        own = sorted(self.tags.for_address(address), key=_rank)
        root = self.uf.root_of(address) if self.uf else None
        inherited: list[Tag] = []
        if root is not None and self.uf is not None:
            if root not in self._cluster_tags:
                members = self.uf.members(root, self.cluster_member_limit)
                self._cluster_tags[root] = [t for ts in self.tags.for_addresses(members).values() for t in ts]
            inherited = sorted((t for t in self._cluster_tags[root] if t.address != address), key=_rank)
        ordered = own + inherited
        best = ordered[0] if ordered else None
        risk = max((self.taxonomy.risk_of_tag(t) for t in ordered), key=RISK_ORDER.__getitem__, default="none")
        # A tag stops a trace by its entity category or by its abuse (many risky tags are
        # category "unknown" + abuse "ransomware"); among several matches the riskiest wins, so a
        # sanctioned exchange stops as "sanctioned", not "exchange".
        matches = [c for t in ordered for c in (t.abuse, t.category) if c in self.stop]
        stop = max(matches, key=lambda c: RISK_ORDER[self.taxonomy.risk(c)], default=None)
        info = AddressInfo(address=address, tags=tuple(ordered), cluster=root,
                           category=best.category if best else None, label=best.label if best else None,
                           risk=risk, stop_category=stop)
        self._cache[address] = info
        return info
