"""The intel database (labels, clusters, cases): one SQLite file, schema created on open."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY, address TEXT NOT NULL, label TEXT NOT NULL,
        category TEXT NOT NULL, abuse TEXT, actor TEXT, confidence TEXT NOT NULL,
        confidence_level INTEGER NOT NULL, source TEXT NOT NULL, pack TEXT NOT NULL,
        is_cluster_definer INTEGER NOT NULL DEFAULT 0, lastmod TEXT,
        created_by TEXT NOT NULL DEFAULT 'import', UNIQUE (address, label, pack))""",
    "CREATE INDEX IF NOT EXISTS tags_address ON tags (address)",
    "CREATE INDEX IF NOT EXISTS tags_label ON tags (label)",
    "CREATE TABLE IF NOT EXISTS coinbase_rules (tag TEXT PRIMARY KEY, pool TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS addr_cluster (address TEXT PRIMARY KEY, root TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS addr_cluster_root ON addr_cluster (root)",
    """CREATE TABLE IF NOT EXISTS clusters (
        root TEXT PRIMARY KEY, size INTEGER NOT NULL, partial INTEGER NOT NULL DEFAULT 1,
        capped INTEGER NOT NULL DEFAULT 0, expanded_at REAL, calls_used INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS cluster_links (
        a TEXT NOT NULL, b TEXT NOT NULL, txid TEXT NOT NULL, heuristic TEXT NOT NULL,
        PRIMARY KEY (a, b, txid))""",
    """CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
        graph TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS case_watch (
        case_id TEXT NOT NULL REFERENCES cases (id) ON DELETE CASCADE, address TEXT NOT NULL,
        added_at REAL NOT NULL, PRIMARY KEY (case_id, address))""",
]


def open_intel_db(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    for stmt in SCHEMA:
        conn.execute(stmt)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN/COMMIT (ROLLBACK on error). Nested use joins the outer transaction."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
