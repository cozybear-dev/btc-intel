import pytest

from btcintel.cases.store import MAX_GRAPH_BYTES, CaseStore
from btcintel.db import open_intel_db


def store():
    now = [1000.0]
    s = CaseStore(open_intel_db(":memory:"), clock=lambda: now[0])
    return s, now


def test_crud_and_ordering():
    s, now = store()
    a = s.create("Bitget 2026")
    now[0] = 1001
    b = s.create("Colonial", notes="ransom", graph={"nodes": [{"id": "x"}]})
    assert [c.id for c in s.list()] == [b.id, a.id] and s.list()[0].nodes == 1
    now[0] = 1002
    updated = s.update(a.id, notes="started", graph={"nodes": [1, 2]})
    assert updated.notes == "started" and updated.updated_at == 1002 and updated.name == "Bitget 2026"
    assert s.list()[0].id == a.id
    assert s.update("missing", notes="x") is None
    assert s.delete(b.id) and not s.delete(b.id) and s.get(b.id) is None


def test_watchlist_and_cascade():
    s, _ = store()
    c = s.create("w")
    assert s.watch(c.id, "bc1QNTNDGQFX46WKS63JEP34CJK3PW63ES86KP45C6")
    assert s.get(c.id).watch == ["bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"]
    assert not s.watch("missing", "x")
    assert s.unwatch(c.id, "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6") and s.get(c.id).watch == []
    s.watch(c.id, "a")
    s.delete(c.id)
    assert s.conn.execute("SELECT COUNT(*) FROM case_watch").fetchone()[0] == 0


def test_graph_size_limit():
    s, _ = store()
    with pytest.raises(ValueError, match="graph too large"):
        s.create("big", graph={"blob": "x" * (MAX_GRAPH_BYTES + 1)})
