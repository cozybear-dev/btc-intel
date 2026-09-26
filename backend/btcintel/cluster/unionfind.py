"""Persistent union-find over addresses (SQLite). Union by size; roots are member addresses."""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel

from btcintel.chain.validate import normalize_address
from btcintel.db import transaction


class ClusterMeta(BaseModel):
    root: str
    size: int
    partial: bool
    capped: bool
    expanded_at: float | None
    calls_used: int


class UnionFind:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def root_of(self, address: str) -> str | None:
        row = self.conn.execute(
            "SELECT root FROM addr_cluster WHERE address = ?", (normalize_address(address),)
        ).fetchone()
        return row["root"] if row else None

    def find(self, address: str) -> str:
        a = normalize_address(address)
        root = self.root_of(a)
        if root is not None:
            return root
        with transaction(self.conn):
            self.conn.execute("INSERT INTO addr_cluster (address, root) VALUES (?, ?)", (a, a))
            self.conn.execute("INSERT OR IGNORE INTO clusters (root, size) VALUES (?, 1)", (a,))
        return a

    def size(self, root: str) -> int:
        row = self.conn.execute("SELECT size FROM clusters WHERE root = ?", (root,)).fetchone()
        return int(row["size"]) if row else 0

    def union(self, a: str, b: str, *, txid: str | None = None, heuristic: str = "H-CIOH") -> str:
        with transaction(self.conn):
            ra, rb = self.find(a), self.find(b)
            if txid is not None:
                self.conn.execute(
                    "INSERT OR IGNORE INTO cluster_links (a, b, txid, heuristic) VALUES (?, ?, ?, ?)",
                    (normalize_address(a), normalize_address(b), txid, heuristic),
                )
            if ra == rb:
                return ra
            sa, sb = self.size(ra), self.size(rb)
            if sa < sb or (sa == sb and rb < ra):
                ra, rb, sa, sb = rb, ra, sb, sa
            absorbed = self.conn.execute(
                "SELECT partial, capped, calls_used FROM clusters WHERE root = ?", (rb,)
            ).fetchone()
            self.conn.execute("UPDATE addr_cluster SET root = ? WHERE root = ?", (ra, rb))
            self.conn.execute(
                "UPDATE clusters SET size = ?, partial = MAX(partial, ?), capped = MAX(capped, ?), "
                "calls_used = calls_used + ? WHERE root = ?",
                (sa + sb, absorbed["partial"], absorbed["capped"], absorbed["calls_used"], ra),
            )
            self.conn.execute("DELETE FROM clusters WHERE root = ?", (rb,))
            return ra

    def members(self, root: str, limit: int | None = None) -> list[str]:
        rows = self.conn.execute(
            "SELECT address FROM addr_cluster WHERE root = ? ORDER BY address LIMIT ?",
            (root, -1 if limit is None else limit),
        )
        return [r["address"] for r in rows]

    def meta(self, root: str) -> ClusterMeta | None:
        r = self.conn.execute("SELECT * FROM clusters WHERE root = ?", (root,)).fetchone()
        if r is None:
            return None
        return ClusterMeta(root=r["root"], size=r["size"], partial=bool(r["partial"]),
                           capped=bool(r["capped"]), expanded_at=r["expanded_at"],
                           calls_used=r["calls_used"])

    def set_meta(self, root: str, *, partial: bool | None = None, capped: bool | None = None,
                 calls_used_add: int = 0, expanded_at: float | None = None) -> None:
        self.find(root)
        self.conn.execute(
            "UPDATE clusters SET partial = COALESCE(?, partial), capped = COALESCE(?, capped), "
            "calls_used = calls_used + ?, expanded_at = COALESCE(?, expanded_at) WHERE root = ?",
            (None if partial is None else int(partial), None if capped is None else int(capped),
             calls_used_add, expanded_at, self.find(root)),
        )

    def links(self, root: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT l.a, l.b, l.txid, l.heuristic FROM cluster_links l "
            "JOIN addr_cluster c ON c.address = l.a WHERE c.root = ? ORDER BY l.txid LIMIT ?",
            (root, limit),
        )
        return [dict(r) for r in rows]
