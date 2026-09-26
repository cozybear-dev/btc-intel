from hypothesis import given, settings
from hypothesis import strategies as st

from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db


def uf() -> UnionFind:
    return UnionFind(open_intel_db(":memory:"))


def test_find_creates_singletons_and_union_merges():
    u = uf()
    assert u.root_of("a") is None
    assert u.find("a") == "a" and u.size("a") == 1
    root = u.union("a", "b", txid="t1")
    assert root == "a" and u.find("b") == "a" and u.size("a") == 2
    assert u.union("b", "a") == "a"
    assert sorted(u.members("a")) == ["a", "b"]
    assert u.links("a") == [{"a": "a", "b": "b", "txid": "t1", "heuristic": "H-CIOH"}]


def test_larger_cluster_absorbs_smaller_and_meta_merges():
    u = uf()
    u.union("a", "b")
    u.union("a", "c")
    u.set_meta("z", partial=False)
    u.find("z")
    u.set_meta("z", capped=True, calls_used_add=7)
    assert u.union("z", "c") == "a"
    meta = u.meta("a")
    assert meta.size == 4 and meta.capped and meta.calls_used == 7 and u.meta("z") is None


def test_bech32_addresses_are_normalised():
    u = uf()
    addr = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
    u.find(addr.upper())
    assert u.root_of(addr) == addr


@given(st.lists(st.tuples(st.integers(0, 11), st.integers(0, 11)), max_size=40))
@settings(max_examples=150, deadline=None)
def test_matches_reference_partition(pairs):
    u = uf()
    names = [f"addr{i}" for i in range(12)]
    parent = list(range(12))

    def ref(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        u.union(names[a], names[b])
        ra, rb = ref(a), ref(b)
        if ra != rb:
            parent[ra] = rb
    for i in range(12):
        for j in range(12):
            assert (u.find(names[i]) == u.find(names[j])) == (ref(i) == ref(j))
    roots = {u.find(n) for n in names}
    assert sum(u.size(r) for r in roots) == 12
    assert all(u.size(r) == len(u.members(r)) for r in roots)
