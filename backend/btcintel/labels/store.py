"""Attribution tags (address → label/category/abuse) with provenance and confidence."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, computed_field

from btcintel.chain.validate import normalize_address
from btcintel.db import transaction

# GraphSense TagPack confidence taxonomy (graphsense-lib tagpack/db/confidence.csv)
CONFIDENCE_LEVELS: dict[str, int] = {
    "override": 100, "ownership": 100, "ledger_immanent": 100, "manual_transaction": 90,
    "service_api": 70, "forensic_investigation": 70, "authority_data": 60, "trusted_provider": 50,
    "service_data": 50, "forensic": 50, "untrusted_transaction": 40, "web_crawl": 20,
    "heuristic": 10, "unknown": 5,
}

_COLUMNS = (
    "address", "label", "category", "abuse", "actor", "confidence", "confidence_level", "source",
    "pack", "is_cluster_definer", "lastmod", "created_by",
)


class Tag(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    address: str
    label: str
    category: str
    abuse: str | None = None
    actor: str | None = None
    confidence: str = "unknown"
    source: str
    pack: str
    is_cluster_definer: bool = False
    lastmod: str | None = None
    created_by: str = "import"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confidence_level(self) -> int:
        return CONFIDENCE_LEVELS.get(self.confidence, 5)


def _row(t: Tag) -> tuple:
    return (
        normalize_address(t.address), t.label, t.category, t.abuse, t.actor, t.confidence,
        t.confidence_level, t.source, t.pack, int(t.is_cluster_definer), t.lastmod, t.created_by,
    )


def _tag(r: sqlite3.Row) -> Tag:
    return Tag(
        id=r["id"], address=r["address"], label=r["label"], category=r["category"], abuse=r["abuse"],
        actor=r["actor"], confidence=r["confidence"], source=r["source"], pack=r["pack"],
        is_cluster_definer=bool(r["is_cluster_definer"]), lastmod=r["lastmod"],
        created_by=r["created_by"],
    )


class TagStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, tag: Tag) -> int:
        cur = self.conn.execute(
            f"INSERT OR REPLACE INTO tags ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' * len(_COLUMNS))})",
            _row(tag),
        )
        return int(cur.lastrowid)

    def add_many(self, tags: Iterable[Tag]) -> int:
        rows = [_row(t) for t in tags]
        with transaction(self.conn):
            self.conn.executemany(
                f"INSERT OR REPLACE INTO tags ({', '.join(_COLUMNS)}) "
                f"VALUES ({', '.join('?' * len(_COLUMNS))})",
                rows,
            )
        return len(rows)

    def get(self, tag_id: int) -> Tag | None:
        r = self.conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        return _tag(r) if r else None

    def for_address(self, address: str) -> list[Tag]:
        rows = self.conn.execute(
            "SELECT * FROM tags WHERE address = ? ORDER BY confidence_level DESC, label",
            (normalize_address(address),),
        )
        return [_tag(r) for r in rows]

    def for_addresses(self, addresses: Iterable[str]) -> dict[str, list[Tag]]:
        wanted = list(dict.fromkeys(normalize_address(a) for a in addresses))
        out: dict[str, list[Tag]] = {}
        for i in range(0, len(wanted), 500):
            chunk = wanted[i : i + 500]
            rows = self.conn.execute(
                f"SELECT * FROM tags WHERE address IN ({', '.join('?' * len(chunk))}) "
                "ORDER BY confidence_level DESC, label",
                chunk,
            )
            for r in rows:
                out.setdefault(r["address"], []).append(_tag(r))
        return out

    def search(self, q: str, limit: int = 50) -> list[Tag]:
        like = f"%{q}%"
        rows = self.conn.execute(
            "SELECT * FROM tags WHERE label LIKE ? OR actor LIKE ? OR address = ? "
            "ORDER BY confidence_level DESC, label LIMIT ?",
            (like, like, q, limit),
        )
        return [_tag(r) for r in rows]

    def by_pack(self, pack: str) -> list[Tag]:
        return [_tag(r) for r in self.conn.execute("SELECT * FROM tags WHERE pack = ? ORDER BY id", (pack,))]

    def packs(self) -> list[tuple[str, int]]:
        rows = self.conn.execute("SELECT pack, COUNT(*) AS n FROM tags GROUP BY pack ORDER BY pack")
        return [(r["pack"], r["n"]) for r in rows]

    def delete(self, tag_id: int) -> bool:
        return self.conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,)).rowcount > 0

    def delete_pack(self, pack: str) -> int:
        return self.conn.execute("DELETE FROM tags WHERE pack = ?", (pack,)).rowcount

    def set_coinbase_rules(self, rules: Iterable[tuple[str, str]]) -> int:
        clean = {tag: pool for tag, pool in rules if tag}
        with transaction(self.conn):
            self.conn.execute("DELETE FROM coinbase_rules")
            self.conn.executemany("INSERT INTO coinbase_rules (tag, pool) VALUES (?, ?)", clean.items())
        return len(clean)

    def coinbase_rules(self) -> list[tuple[str, str]]:
        rows = self.conn.execute("SELECT tag, pool FROM coinbase_rules ORDER BY length(tag) DESC, tag")
        return [(r["tag"], r["pool"]) for r in rows]
