import pytest

from tests.analysis_scenario import R, build_funded, run_analysis
from tests.fakes import FakeChain


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
