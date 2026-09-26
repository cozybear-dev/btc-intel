from btcintel.cluster.expand import ExpandPolicy, cluster_conflicts, expand_cluster
from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db
from btcintel.labels.store import Tag, TagStore
from tests import cj_samples as s
from tests.builders import mk_tx
from tests.fakes import FakeChain


def world():
    conn = open_intel_db(":memory:")
    tx1 = mk_tx([("A", 50_000), ("B", 60_000)], [("X", 100_000)])
    tx2 = mk_tx([("B", 70_000), ("C", 80_000)], [("Y", 140_000)])
    mix = s.whirlpool_mix()
    mix = mix.model_copy(update={"vin": [mix.vin[0].model_copy(update={
        "prevout": mix.vin[0].prevout.model_copy(update={"address": "C"})})] + mix.vin[1:]})
    tx4 = mk_tx([("D", 10_000)], [("Z", 9_000)])
    return FakeChain([tx1, tx2, mix, tx4]), UnionFind(conn), TagStore(conn)


async def test_expand_follows_cioh_and_skips_coinjoins():
    chain, uf, tags = world()
    events = []
    r = await expand_cluster("A", chain, uf, tags, progress=events.append)
    assert (r.root, r.size, r.new_links, r.partial, r.capped) == ("A", 3, 2, False, False)
    assert sorted(uf.members("A")) == ["A", "B", "C"]
    assert uf.root_of("bc1-sample-1") is None
    assert events and events[-1]["type"] == "progress"
    assert uf.meta("A").partial is False and uf.meta("A").calls_used == r.calls_used


async def test_expand_caps_cluster_size():
    chain, uf, tags = world()
    r = await expand_cluster("A", chain, uf, tags, ExpandPolicy(max_addresses=2))
    assert r.capped and r.partial and r.size == 2


async def test_expand_budget_marks_partial():
    chain, uf, tags = world()
    r = await expand_cluster("A", chain, uf, tags, ExpandPolicy(max_calls=1))
    assert r.partial and r.calls_used == 1


async def test_truncated_history_marks_partial():
    chain, uf, tags = world()
    r = await expand_cluster("B", chain, uf, tags, ExpandPolicy(max_txs_per_address=1))
    assert r.partial


async def test_conflicting_entity_labels_reported():
    chain, uf, tags = world()
    tags.add_many([
        Tag(address="A", label="Binance", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="C", label="Kraken", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="B", label="some person", category="individual", confidence="authority_data", source="s", pack="p"),
    ])
    r = await expand_cluster("A", chain, uf, tags)
    assert [c.labels for c in r.conflicts] == [["binance", "kraken"]]
    assert cluster_conflicts("A", uf, tags) == r.conflicts
