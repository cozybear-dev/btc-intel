from btcintel.chain.cache import Cache


def test_roundtrip_and_missing(tmp_path):
    c = Cache(tmp_path / "c.db")
    c.put_json("k", {"a": [1, 2]}, ttl=None)
    assert c.get_json("k") == {"a": [1, 2]}
    assert c.get_json("missing") is None


def test_ttl_expiry_and_purge(tmp_path):
    now = [1000.0]
    c = Cache(tmp_path / "c.db", clock=lambda: now[0])
    c.put_json("k", 1, ttl=10)
    c.put_json("forever", 2, ttl=None)
    now[0] = 1009.9
    assert c.get_json("k") == 1
    now[0] = 1010.0
    assert c.get_json("k") is None
    assert c.get_json("forever") == 2
    assert c.purge_expired() == 1


def test_overwrite_replaces_value_and_ttl(tmp_path):
    now = [0.0]
    c = Cache(tmp_path / "c.db", clock=lambda: now[0])
    c.put_json("k", "old", ttl=1)
    c.put_json("k", "new", ttl=None)
    now[0] = 100
    assert c.get_json("k") == "new"


def test_persists_across_instances(tmp_path):
    Cache(tmp_path / "c.db").put_json("k", [1], ttl=None)
    assert Cache(tmp_path / "c.db").get_json("k") == [1]


def test_memory_cache_and_nested_dir(tmp_path):
    Cache(":memory:").put_json("k", 1, ttl=None)
    c = Cache(tmp_path / "a" / "b" / "c.db")
    c.put_json("x", True, ttl=None)
    assert c.get_json("x") is True
