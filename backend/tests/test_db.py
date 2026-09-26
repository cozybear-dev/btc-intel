import pytest

from btcintel.db import open_intel_db, transaction


def test_schema_created(tmp_path):
    conn = open_intel_db(tmp_path / "x" / "intel.db")
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"tags", "coinbase_rules", "addr_cluster", "clusters", "cluster_links", "cases", "case_watch"} <= names


def test_transaction_rolls_back_on_error():
    conn = open_intel_db(":memory:")
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute("INSERT INTO coinbase_rules(tag, pool) VALUES ('/x/', 'X')")
        raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM coinbase_rules").fetchone()[0] == 0


def test_nested_transactions_commit_once():
    conn = open_intel_db(":memory:")
    with transaction(conn):
        with transaction(conn):
            conn.execute("INSERT INTO coinbase_rules(tag, pool) VALUES ('/a/', 'A')")
        conn.execute("INSERT INTO coinbase_rules(tag, pool) VALUES ('/b/', 'B')")
    assert conn.execute("SELECT COUNT(*) FROM coinbase_rules").fetchone()[0] == 2
    assert not conn.in_transaction
