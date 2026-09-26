import pytest

from btcintel.heuristics.base import Context
from btcintel.heuristics.change import (
    change_heuristic,
    detect_change,
    detect_change_offline,
    remainder_output,
    trailing_zeros,
)
from tests import cj_samples as s
from tests.builders import mk_tx
from tests.fakes import FakeChain


def votes_by_signal(result):
    return {(v.signal, v.output) for v in result.votes}


async def test_self_change():
    tx = mk_tx([("a", 100_000)], [("b", 30_000), ("a", 69_000)])
    r = await detect_change(tx)
    assert r.applicable and r.change_output == 1 and ("H-CHG-SELF", 1) in votes_by_signal(r)
    assert r.probabilities[1] == pytest.approx(0.982, abs=1e-3)


async def test_script_type_and_round_agree():
    tx = mk_tx([("a", 1_000_000, "p2pkh")], [("b", 400_000, "v0_p2wpkh"), ("c", 599_000, "p2pkh")])
    r = await detect_change(tx)
    assert r.change_output == 1
    assert {("H-CHG-SCRIPT", 1), ("H-CHG-SCRIPT", 0), ("H-CHG-ROUND", 1), ("H-CHG-ROUND", 0)} <= votes_by_signal(r)
    assert r.probabilities[1] == pytest.approx(0.9002, abs=1e-3)


async def test_round_payment_only():
    r = await detect_change(mk_tx([("a", 250_000)], [("b", 100_000), ("c", 149_000)]))
    assert r.change_output == 1 and r.probabilities[1] == pytest.approx(0.7685, abs=1e-3)


async def test_unnecessary_input():
    r = await detect_change(mk_tx([("a", 50_000), ("b", 60_000)], [("c", 95_000), ("d", 14_000)]))
    assert r.change_output == 1 and ("H-CHG-UNNECESSARY", 1) in votes_by_signal(r)


async def test_no_signal_means_undetermined():
    r = await detect_change(mk_tx([("a", 800_000)], [("b", 123_456), ("c", 654_321)]))
    assert r.applicable and r.change_output is None and r.probabilities == {0: 0.5, 1: 0.5}


@pytest.mark.parametrize("tx,reason", [
    (s.whirlpool_mix(), "coinjoin:whirlpool"),
    (mk_tx([("a", 10_000)], [(f"o{i}", 1_000) for i in range(6)]), "more than 4 outputs (batch payment)"),
    (mk_tx([("a", 10_000)], [("b", 9_000)]), "fewer than two outputs"),
    (mk_tx([(None, 0)], [("m", 1), ("n", 2)], coinbase=True), "coinbase"),
])
async def test_not_applicable(tx, reason):
    r = await detect_change(tx)
    assert not r.applicable and r.reason == reason and r.change_output is None


async def test_fingerprint_continuity_uses_spending_transactions():
    t = mk_tx([("a", 1_000_000)], [("b", 123_456), ("c", 654_321)])
    other_wallet = mk_tx([(t, 0)], [("x", 120_000)], version=1)
    same_wallet = mk_tx([(t, 1)], [("y", 650_000)])
    r = await detect_change(t, Context(chain=FakeChain([t, other_wallet, same_wallet])))
    assert r.change_output == 1
    assert ("H-CHG-FPCONT", 1) in votes_by_signal(r) and ("H-CHG-FPCONT", 0) in votes_by_signal(r)


async def test_offline_matches_async_without_chain():
    tx = mk_tx([("a", 250_000)], [("b", 100_000), ("c", 149_000)])
    assert detect_change_offline(tx) == await detect_change(tx)


def test_remainder_output_falls_back_to_largest():
    assert remainder_output(mk_tx([("a", 800_000)], [("b", 123_456), ("c", 654_321)])) == 1
    assert remainder_output(mk_tx([("a", 100_000)], [("a", 90_000), ("b", 9_000)])) == 0


def test_trailing_zeros():
    assert [trailing_zeros(v) for v in (0, 7, 1_000_000, 149_000)] == [0, 0, 6, 3]


async def test_heuristic_finding():
    tx = mk_tx([("a", 100_000)], [("b", 30_000), ("a", 69_000)])
    (f,) = await change_heuristic(tx, Context())
    assert f.heuristic == "H-CHG" and f.subject == f"out:{tx.txid}:1" and f.label == "change"
    assert f.evidence["votes"][0]["signal"] == "H-CHG-SELF"
    assert await change_heuristic(mk_tx([("a", 800_000)], [("b", 123_456), ("c", 654_321)]), Context()) == []
