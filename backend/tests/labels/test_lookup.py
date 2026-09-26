from btcintel.catalog.loader import load_catalog
from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db
from btcintel.labels.lookup import LabelLookup
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))


def test_own_and_cluster_tags_risk_and_stop():
    conn = open_intel_db(":memory:")
    tags, uf = TagStore(conn), UnionFind(conn)
    uf.union("hot", "deposit")
    tags.add_many([
        Tag(address="hot", label="Binance", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="bad", label="OFAC person", category="individual", abuse="sanctioned",
            confidence="authority_data", source="s", pack="p"),
    ])
    lookup = LabelLookup(tags, TAX, uf)
    dep = lookup.lookup("deposit")
    assert dep.cluster == "deposit" or dep.cluster == "hot"
    assert dep.label == "Binance" and dep.category == "exchange" and dep.stop_category == "exchange"
    assert dep.risk == "low"
    bad = lookup.lookup("bad")
    assert bad.risk == "severe" and bad.stop_category is None and bad.cluster is None
    none = lookup.lookup("nobody")
    assert (none.label, none.risk, none.tags) == (None, "none", ())
    assert LabelLookup(tags, TAX, uf, stop_categories=[]).lookup("hot").stop_category is None
    assert dep.to_dict()["tags"][0]["label"] == "Binance"


def test_stop_matches_abuse_and_prefers_the_riskiest():
    tags = TagStore(open_intel_db(":memory:"))
    tags.add_many([
        Tag(address="rw", label="LockBit", category="unknown", abuse="ransomware", confidence="forensic",
            source="s", pack="p"),
        Tag(address="gx", label="Garantex", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="gx", label="Garantex (OFAC)", category="organization", abuse="sanctioned",
            confidence="forensic", source="s", pack="p"),
    ])
    default = LabelLookup(tags, TAX)
    assert default.lookup("rw").stop_category is None  # abuse ids are not default stop categories
    assert default.lookup("gx").stop_category == "exchange"
    everything = LabelLookup(tags, TAX, stop_categories=set(TAX.categories) - {"unknown"})
    assert everything.lookup("rw").stop_category == "ransomware"
    assert everything.lookup("gx").stop_category == "sanctioned"
