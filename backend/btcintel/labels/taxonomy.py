"""Category taxonomy from the catalog: GraphSense concept mapping and risk levels."""

from __future__ import annotations

from collections.abc import Iterable

from btcintel.catalog.schema import RISK_ORDER, Catalog, Category
from btcintel.labels.store import Tag


class Taxonomy:
    def __init__(self, categories: Iterable[Category]) -> None:
        self.categories: dict[str, Category] = {c.id: c for c in categories}
        self._by_concept = {gs.lower(): c.id for c in self.categories.values() for gs in c.gs_concepts}

    @classmethod
    def from_catalog(cls, cat: Catalog) -> Taxonomy:
        return cls(cat.categories)

    def normalize(self, concept: str | None) -> str | None:
        if not concept:
            return None
        key = str(concept).strip().lower()
        if key in self.categories:
            return key
        return self._by_concept.get(key)

    def risk(self, category_id: str | None) -> str:
        c = self.categories.get(category_id or "")
        return c.risk if c else "none"

    def risk_of_tag(self, tag: Tag) -> str:
        return max((self.risk(tag.category), self.risk(tag.abuse)), key=RISK_ORDER.__getitem__)

    def default_stop_categories(self) -> set[str]:
        return {c.id for c in self.categories.values() if c.stop_trace}
