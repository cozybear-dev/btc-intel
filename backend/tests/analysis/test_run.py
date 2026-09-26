import pytest

from btcintel.analysis.models import AnalysisPolicy
from btcintel.analysis.run import summarize_cluster
from btcintel.cluster.expand import ExpandResult
from btcintel.labels.store import Tag
from tests.analysis_scenario import TAX, A, R, build_funded, run_analysis, stores
from tests.builders import ADDR, mk_tx
from tests.fakes import FakeChain
from tests.scenario import EX


async def test_analysis_finds_ransomware_source_and_exchange_destination():
    report, _ = await run_analysis(FakeChain(build_funded().txs))
    src = {b.label: b for b in report.sources.buckets}
    assert src["LockBit"].key == "ransomware" and src["LockBit"].min_hops == 1
    assert src["LockBit"].share == pytest.approx(1.0)
    dst = {b.label: b for b in report.destinations.buckets}
    assert dst["Example Exchange"].share == pytest.approx(1_000_000 / 1_500_000, rel=1e-3)
    assert dst["Still unspent"].min_hops == 1
    assert report.verdict.level == "severe" and report.verdict.final
    assert [r.rule for r in report.verdict.reasons] == ["direct_severe", "high_share", "low_only"]
    assert report.profile.received_external == 1_500_000 and report.cluster.size == 1
    assert report.depth == "quick" and report.calls_used > 0


async def test_analysis_streams_sections_graph_and_one_done():
    report, events = await run_analysis(FakeChain(build_funded().txs))
    sections = [e["name"] for e in events if e["type"] == "section"]
    assert sections[:2] == ["profile", "verdict"] and sections[-1] == "verdict"
    assert {"cluster", "sources", "destinations"} <= set(sections)
    first_verdict = next(e for e in events if e["type"] == "section" and e["name"] == "verdict")
    assert first_verdict["data"]["final"] is False
    assert any(e["type"] == "nodes" for e in events) and any(e["type"] == "stop" for e in events)
    assert [e["type"] for e in events].count("done") == 1 and events[-1]["type"] == "done"
    assert events[-1]["calls_used"] == report.calls_used and not events[-1]["incomplete"]


async def test_a_labeled_address_still_shows_where_its_funds_went():
    report, _ = await run_analysis(FakeChain(build_funded().txs), address=R)
    assert report.verdict.level == "severe" and report.verdict.reasons[0].rule == "own_label"
    assert "Example Exchange" in {b.label for b in report.destinations.buckets}
    assert {b.kind for b in report.sources.buckets} == {"coinbase"}


async def test_unused_address_gives_an_empty_but_complete_report():
    report, _ = await run_analysis(FakeChain([]))
    assert report.profile.txs_seen == 0
    assert report.sources.buckets == [] and report.destinations.buckets == []
    assert report.verdict.level == "none" and report.verdict.coverage.startswith("No incoming funds")


async def test_a_failing_trace_direction_is_reported_not_fatal():
    sc = build_funded()
    # R untagged and its funding coinbase missing: the backward trace hits NotFound for sc.cb
    report, events = await run_analysis(FakeChain([sc.pay, sc.spend]), tagged=False)
    assert report.sources.error.startswith("NotFound") and report.sources.buckets[0].kind == "remainder"
    assert "Example Exchange" in {b.label for b in report.destinations.buckets}
    assert events[-1]["type"] == "done" and events[-1]["incomplete"]


async def test_busy_address_is_still_traced_past_its_own_history():
    # 65 receipts (> quick trace_txs = 60), then everything is swept to a darknet market
    cb = mk_tx([(None, 0)], [(ADDR[10], 30_000)] * 65, coinbase=True)
    receipts = [mk_tx([(cb, i)], [(A, 20_000)]) for i in range(65)]
    sweep = mk_tx([(r, 0) for r in receipts], [(ADDR[11], 1_290_000)])
    hydra = Tag(address=ADDR[11], label="Hydra", category="darknet_market", confidence="authority_data",
                source="t", pack="t")
    # FakeChain has no tx cache, so give the traces enough calls to isolate the tx cap
    policy = AnalysisPolicy.quick().model_copy(update={"trace_calls": 1000})
    report, _ = await run_analysis(FakeChain([cb, *receipts, sweep]), extra_tags=[hydra], policy=policy)
    dst = {b.label: b for b in report.destinations.buckets}
    assert dst["Hydra"].min_hops == 1 and dst["Hydra"].share > 0.99
    assert report.verdict.level == "severe"


async def test_a_severe_tag_beyond_the_first_ten_still_counts():
    services = [Tag(address=A, label=f"Service {i:02d}", category="exchange", confidence="service_data",
                    source="t", pack="t") for i in range(12)]
    theft = Tag(address=A, label="Zeta theft", category="unknown", abuse="theft", confidence="web_crawl",
                source="t", pack="t")
    report, _ = await run_analysis(FakeChain(build_funded().txs), tagged=False, extra_tags=[*services, theft])
    assert report.verdict.level == "severe"
    assert report.verdict.reasons[0].text == "Labeled Zeta theft (theft, t)"
    assert report.profile.info["tags"][0]["label"] == "Zeta theft" and len(report.profile.info["tags"]) == 10


def test_cluster_top_labels_put_the_riskiest_first():
    members = ADDR[10:14]
    common = [Tag(address=a, label="Big Exchange", category="exchange", confidence="service_data", source="t",
                  pack="t") for a in members[:3]]
    helix = Tag(address=members[3], label="Helix", category="mixing_service", confidence="web_crawl", source="t",
                pack="t")
    tags, uf = stores(tagged=False, extra_tags=[*common, helix])
    for a in members[1:]:
        root = uf.union(members[0], a)
    result = ExpandResult(root=root, size=len(members), partial=False, capped=False, calls_used=0, new_links=0,
                          conflicts=[])
    top = summarize_cluster(result, uf, tags, TAX).top_labels
    assert [(t["label"], t["count"]) for t in top] == [("Helix", 1), ("Big Exchange", 3)]


async def test_a_labeled_address_is_traced_through_its_own_change():
    c, x = ADDR[12], ADDR[13]
    cb = mk_tx([(None, 0)], [(R, 1_000_000), (c, 10_000)], coinbase=True)
    link = mk_tx([(cb, 0), (cb, 1)], [(R, 1_005_000)])        # R and C co-spend: CIOH links them
    pay = mk_tx([(link, 0)], [(x, 500_000), (c, 504_000)])     # R pays X, change to its sibling C
    cash = mk_tx([(pay, 1)], [(EX, 503_000)])                  # C cashes out at the exchange
    report, _ = await run_analysis(FakeChain([cb, link, pay, cash]), address=R)
    assert report.cluster.size == 2
    kinds = {(b.kind, b.label) for b in report.destinations.buckets}
    assert ("labeled", "Example Exchange") in kinds
    assert not any(k == "own_cluster" for k, _ in kinds)
