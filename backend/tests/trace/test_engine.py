import pytest

from btcintel.trace.engine import TracePolicy, TraceSeed, trace
from tests import cj_samples as s
from tests.builders import ADDR, mk_tx
from tests.fakes import FakeChain
from tests.scenario import EX, H1, H3, UNTAGGED, M, U, build_scenario, make_labels


def stops(result):
    return {(st.node, st.reason) for st in result.stops}


def tx_ids(result):
    return {n.id for n in result.nodes if n.kind == "tx"}


async def test_forward_trace_reaches_services_and_unspent():
    sc = build_scenario()
    events = []
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(), chain=FakeChain(sc.txs),
                    labels=make_labels(), emit=events.append)
    assert {(f"addr:{EX}", "labeled"), (f"addr:{M}", "labeled"), (f"addr:{U}", "unspent")} <= stops(r)
    assert tx_ids(r) == {f"tx:{t.txid}" for t in sc.txs}
    edges = {e.id: e for e in r.edges}
    assert edges[f"out:{sc.t1.txid}:0"].taint == pytest.approx(100_000)
    assert edges[f"out:{sc.t2.txid}:0"].taint == pytest.approx(498_000)
    assert not r.incomplete and r.txs_expanded == 4
    assert {e["type"] for e in events} >= {"nodes", "edges", "stop", "done"} and events[-1]["type"] == "done"


async def test_max_hops():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(max_hops=1), chain=FakeChain(sc.txs),
                    labels=make_labels())
    assert f"tx:{sc.t2.txid}" not in tx_ids(r) and (f"addr:{H3}", "max_hops") in stops(r)


async def test_min_value():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(min_value_sats=450_000),
                    chain=FakeChain(sc.txs), labels=make_labels())
    assert f"tx:{sc.t3.txid}" not in tx_ids(r)
    assert any(reason == "min_value" for _, reason in stops(r))


async def test_coinjoin_stop_and_through():
    seed = mk_tx([(ADDR[9], 2_000_000)], [(ADDR[10], 1_006_050), (ADDR[11], 900_000)])
    mix = s.whirlpool_mix()
    mix = mix.model_copy(update={"vin": [mix.vin[0].model_copy(update={
        "prev_txid": seed.txid, "prev_vout": 0, "prevout": seed.vout[0]})] + mix.vin[1:]})
    chain = FakeChain([seed, mix])
    stopped = await trace(TraceSeed(txid=seed.txid, vout=0), TracePolicy(), chain=chain, labels=make_labels())
    assert (f"tx:{mix.txid}", "coinjoin") in stops(stopped)
    through = await trace(TraceSeed(txid=seed.txid, vout=0), TracePolicy(coinjoin="through"),
                          chain=chain, labels=make_labels())
    assert sum(1 for _, reason in stops(through) if reason == "unspent") == 5


async def test_peel_mode_follows_remainder():
    a = UNTAGGED
    p0 = mk_tx([(a[0], 10_000_000)], [(a[1], 500_000), (a[2], 9_490_000)])
    p1 = mk_tx([(p0, 1)], [(a[3], 400_000), (a[4], 9_080_000)])
    p2 = mk_tx([(p1, 1)], [(a[5], 300_000), (a[6], 8_770_000)])
    r = await trace(TraceSeed(txid=p0.txid, vout=1), TracePolicy(peel_mode=True),
                    chain=FakeChain([p0, p1, p2]), labels=make_labels())
    assert {(f"addr:{a[3]}", "peel_off"), (f"addr:{a[5]}", "peel_off"), (f"addr:{a[6]}", "unspent")} <= stops(r)


async def test_backward_to_coinbase_and_labeled_source():
    a = ADDR
    cb = mk_tx([(None, 0)], [(a[0], 312_500_000)], coinbase=True)
    t = mk_tx([(cb, 0)], [(a[1], 100_000_000), (a[2], 212_000_000)])
    t2 = mk_tx([(t, 0)], [(a[3], 99_000_000)])
    chain = FakeChain([cb, t, t2])
    r = await trace(TraceSeed(txid=t2.txid), TracePolicy(direction="backward"), chain=chain, labels=make_labels())
    assert (f"tx:{cb.txid}", "coinbase") in stops(r)
    from btcintel.labels.store import Tag
    labeled = make_labels([Tag(address=a[0], label="Exchange hot wallet", category="exchange",
                               confidence="authority_data", source="t", pack="t")])
    r2 = await trace(TraceSeed(txid=t2.txid), TracePolicy(direction="backward"), chain=chain, labels=labeled)
    assert (f"addr:{a[0]}", "labeled") in stops(r2) and f"tx:{cb.txid}" not in tx_ids(r2)


async def test_budget_exhaustion_marks_incomplete():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(max_calls=2), chain=FakeChain(sc.txs),
                    labels=make_labels())
    assert r.incomplete and "budget" in r.reason and r.calls_used == 2


async def test_source_error_mid_trace_marks_incomplete():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(), chain=FakeChain(sc.txs, fail_on={sc.t1.txid}),
                    labels=make_labels())
    assert r.incomplete and "chain source failed" in r.reason


async def test_max_txs_truncates():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(max_txs=2), chain=FakeChain(sc.txs),
                    labels=make_labels())
    assert r.incomplete and "max_txs" in r.reason and len(tx_ids(r)) == 2


async def test_address_seed():
    sc = build_scenario()
    r = await trace(TraceSeed(address=H1), TracePolicy(), chain=FakeChain(sc.txs), labels=make_labels())
    assert f"tx:{sc.t1.txid}" in tx_ids(r)


async def test_poison_counts_each_tx_once():
    sc = build_scenario()
    join = mk_tx([(sc.theft, 0), (sc.theft, 1)], [(ADDR[12], 998_000)])
    chain = FakeChain([sc.theft, join])
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(taint_model="poison"), chain=chain,
                    labels=make_labels())
    edges = {e.id: e for e in r.edges}
    assert edges[f"out:{join.txid}:0"].taint == pytest.approx(998_000)


@pytest.mark.parametrize("kwargs", [{}, {"txid": "zz"}, {"address": "nope"},
                                    {"txid": "ab" * 32, "address": ADDR[0]},
                                    {"address": ADDR[0], "vout": 1}])
def test_invalid_seeds(kwargs):
    with pytest.raises(ValueError):
        TraceSeed(**kwargs)


def test_seed_normalisation():
    assert TraceSeed(txid="AB" * 32).txid == "ab" * 32
    assert TraceSeed(address=ADDR[1].upper()).address == ADDR[1]


def self_change_chain():
    """a1 receives 999k, then pays 300k twice, returning change to itself each time."""
    a = UNTAGGED
    cb = mk_tx([(None, 0)], [(a[0], 1_000_000)], coinbase=True)
    fund = mk_tx([(cb, 0)], [(a[1], 999_000)])
    s1 = mk_tx([(fund, 0)], [(a[2], 300_000), (a[1], 698_000)])
    s2 = mk_tx([(s1, 1)], [(a[3], 300_000), (a[1], 397_000)])
    return a, cb, fund, s1, s2


async def test_address_seed_forward_counts_self_change_once():
    a, cb, fund, s1, s2 = self_change_chain()
    r = await trace(TraceSeed(address=a[1]), TracePolicy(min_value_sats=1), chain=FakeChain([cb, fund, s1, s2]),
                    labels=make_labels())
    edges = {e.id: e for e in r.edges}
    assert edges[f"out:{s2.txid}:0"].taint == pytest.approx(300_000)
    assert sum(1 for st in r.stops if st.node == f"addr:{a[3]}") == 1
    assert sum(st.taint for st in r.stops) <= 999_000


async def test_address_seed_backward_counts_self_change_once():
    a, cb, fund, s1, s2 = self_change_chain()
    r = await trace(TraceSeed(address=a[1]), TracePolicy(direction="backward", min_value_sats=1),
                    chain=FakeChain([cb, fund, s1, s2]), labels=make_labels())
    edges = {e.id: e for e in r.edges}
    assert edges[f"out:{fund.txid}:0"].taint == pytest.approx(999_000)
    assert sum(st.taint for st in r.stops if st.reason == "coinbase") <= 1_000_000
