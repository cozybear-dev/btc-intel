"""Persistent key/value cache for API responses (zlib-compressed JSON in SQLite)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value BLOB NOT NULL, expires REAL)"
        )
        self._lock = threading.Lock()
        self._clock = clock

    def get_json(self, key: str) -> Any | None:
        with self._lock:
            row = self._db.execute("SELECT value, expires FROM kv WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        value, expires = row
        if expires is not None and expires <= self._clock():
            return None
        return json.loads(zlib.decompress(value))

    def put_json(self, key: str, obj: Any, ttl: float | None) -> None:
        blob = zlib.compress(json.dumps(obj, separators=(",", ":")).encode(), 6)
        expires = None if ttl is None else self._clock() + ttl
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO kv (key, value, expires) VALUES (?, ?, ?)",
                (key, blob, expires),
            )

    def purge_expired(self) -> int:
        with self._lock:
            cur = self._db.execute(
                "DELETE FROM kv WHERE expires IS NOT NULL AND expires <= ?", (self._clock(),)
            )
        return cur.rowcount

    def close(self) -> None:
        self._db.close()
