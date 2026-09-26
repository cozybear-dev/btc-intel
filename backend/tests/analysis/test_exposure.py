import pytest

from btcintel.analysis.exposure import compute_exposure, failed_exposure
from btcintel.catalog.loader import load_catalog
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from btcintel.trace.engine import TracePolicy, TraceResult, TraceSeed
from btcintel.trace.graph import GraphNode, Stop
from tests.builders import ADDR

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))
SEED, RW, EX, EX2 = ADDR[1], ADDR[9], ADDR[2], ADDR[10]


def addr_node(address, *, label, category, risk, stop_category, abuse=None, pack="p"):
    tag = {"address": address, "label": label, "category": category, "abuse": abuse, "pack": pack}
    return GraphNode(id=f"addr:{address}", kind="address", label=label, data={
        "address": address, "tags": [tag], "label": label, "category": category, "risk": risk,
        "stop_category": stop_category})


NODES = [
    addr_node(RW, label="LockBit", category="unknown", abuse="ransomware", risk="severe",
              stop_category="ransomware", pack="ransomwhere"),
    addr_node(EX, label="Binance", category="exchange", risk="low", stop_category="exchange"),
    addr_node(EX2, label="Binance", category="exchange", risk="low", stop_category="exchange"),
]


def result(stops, nodes=NODES, incomplete=False, reason=None):
    return TraceResult(seed=TraceSeed(address=SEED), policy=TracePolicy(), nodes=list(nodes), edges=[],
                       stops=stops, incomplete=incomplete, reason=reason, calls_used=7, txs_expanded=3)


def never(_address):
    return False


def test_buckets_group_stops_and_add_up_to_the_total():
    stops = [Stop(node=f"addr:{RW}", reason="labeled", taint=300_000, hops=2),
             Stop(node=f"addr:{EX}", reason="labeled", taint=400_000, hops=1),
             Stop(node=f"addr:{EX2}", reason="labeled", taint=100_000, hops=3),
             Stop(node=f"addr:{ADDR[8]}", reason="unspent", taint=150_000, hops=2),
             Stop(node=f"addr:{ADDR[11]}", reason="max_hops", taint=40_000, hops=4)]
    e = compute_exposure("backward", result(stops), 1_000_000, taxonomy=TAX, own_cluster=never)
    assert [(b.kind, b.label) for b in e.buckets] == [
        ("labeled", "LockBit"), ("labeled", "Binance"), ("unspent", "Still unspent"),
        ("limits", "Beyond the hop limit"), ("remainder", "Fees or not reached (budget)")]
    rw, ex = e.buckets[0], e.buckets[1]
    assert (rw.key, rw.risk, rw.source, rw.min_hops, rw.share) == ("ransomware", "severe", "ransomwhere", 2, 0.3)
    assert ex.amount == 500_000 and ex.min_hops == 1 and ex.nodes == [f"addr:{EX}", f"addr:{EX2}"]
    assert e.buckets[-1].amount == pytest.approx(10_000)
    assert sum(b.share for b in e.buckets) == pytest.approx(1.0)
    assert e.resolved_share == pytest.approx(0.95)  # limits and remainder are not endpoints
    assert (e.direction, e.total, e.calls_used) == ("backward", 1_000_000, 7)


def test_own_cluster_coinjoin_and_coinbase_buckets():
    stops = [Stop(node=f"addr:{EX}", reason="labeled", taint=200_000, hops=1),
             Stop(node="tx:" + "ab" * 32, reason="coinjoin", taint=300_000, detail="whirlpool", hops=2),
             Stop(node="tx:" + "cd" * 32, reason="coinbase", taint=500_000, hops=3)]
    e = compute_exposure("backward", result(stops), 1_000_000, taxonomy=TAX, own_cluster=lambda a: a == EX)
    by_kind = {b.kind: b for b in e.buckets}
    assert set(by_kind) == {"own_cluster", "coinjoin", "coinbase"}
    assert by_kind["own_cluster"].label == "Binance"
    assert by_kind["coinjoin"].label == "CoinJoin (whirlpool)" and by_kind["coinjoin"].risk == "medium"
    assert by_kind["coinbase"].label == "Newly mined coins"
    assert e.resolved_share == pytest.approx(1.0)


def test_zero_total_and_incomplete_trace():
    e = compute_exposure("forward", result([], incomplete=True, reason="API call budget of 120 exhausted"), 0,
                         taxonomy=TAX, own_cluster=never)
    assert e.buckets == [] and e.resolved_share == 0.0
    assert e.incomplete and "budget" in e.reason


def test_failed_exposure_is_all_remainder():
    e = failed_exposure("forward", 500_000, "NotFound: tx missing")
    assert [(b.kind, b.share) for b in e.buckets] == [("remainder", 1.0)]
    assert e.error == "NotFound: tx missing" and e.incomplete and e.resolved_share == 0.0
    assert failed_exposure("forward", 0, "boom").buckets == []
