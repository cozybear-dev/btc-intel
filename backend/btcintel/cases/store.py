"""Saved investigations: graph state (opaque JSON from the UI), notes and a watchlist."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from btcintel.chain.validate import normalize_address

MAX_GRAPH_BYTES = 10_000_000


class Case(BaseModel):
    id: str
    name: str
    notes: str
    graph: dict[str, Any]
    created_at: float
    updated_at: float
    watch: list[str] = []


class CaseSummary(BaseModel):
    id: str
    name: str
    created_at: float
    updated_at: float
    nodes: int


def _graph_json(graph: dict[str, Any]) -> str:
    text = json.dumps(graph, separators=(",", ":"))
    if len(text.encode()) > MAX_GRAPH_BYTES:
        raise ValueError(f"graph too large (limit {MAX_GRAPH_BYTES} bytes)")
    return text


class CaseStore:
    def __init__(self, conn: sqlite3.Connection, clock: Callable[[], float] = time.time) -> None:
        self.conn = conn
        self._clock = clock

    def create(self, name: str, notes: str = "", graph: dict[str, Any] | None = None) -> Case:
        now = self._clock()
        case_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO cases (id, name, notes, graph, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, name, notes, _graph_json(graph or {}), now, now),
        )
        return self.get(case_id)  # type: ignore[return-value]

    def get(self, case_id: str) -> Case | None:
        r = self.conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if r is None:
            return None
        watch = [w["address"] for w in self.conn.execute(
            "SELECT address FROM case_watch WHERE case_id = ? ORDER BY added_at, address", (case_id,))]
        return Case(id=r["id"], name=r["name"], notes=r["notes"], graph=json.loads(r["graph"]),
                    created_at=r["created_at"], updated_at=r["updated_at"], watch=watch)

    def list(self) -> list[CaseSummary]:
        rows = self.conn.execute("SELECT * FROM cases ORDER BY updated_at DESC, id")
        return [CaseSummary(id=r["id"], name=r["name"], created_at=r["created_at"],
                            updated_at=r["updated_at"], nodes=len(json.loads(r["graph"]).get("nodes", [])))
                for r in rows]

    def update(self, case_id: str, *, name: str | None = None, notes: str | None = None,
               graph: dict[str, Any] | None = None) -> Case | None:
        if self.get(case_id) is None:
            return None
        self.conn.execute(
            "UPDATE cases SET name = COALESCE(?, name), notes = COALESCE(?, notes), "
            "graph = COALESCE(?, graph), updated_at = ? WHERE id = ?",
            (name, notes, None if graph is None else _graph_json(graph), self._clock(), case_id),
        )
        return self.get(case_id)

    def delete(self, case_id: str) -> bool:
        return self.conn.execute("DELETE FROM cases WHERE id = ?", (case_id,)).rowcount > 0

    def watch(self, case_id: str, address: str) -> bool:
        if self.get(case_id) is None:
            return False
        self.conn.execute(
            "INSERT OR IGNORE INTO case_watch (case_id, address, added_at) VALUES (?, ?, ?)",
            (case_id, normalize_address(address), self._clock()),
        )
        return True

    def unwatch(self, case_id: str, address: str) -> bool:
        return self.conn.execute(
            "DELETE FROM case_watch WHERE case_id = ? AND address = ?",
            (case_id, normalize_address(address)),
        ).rowcount > 0
