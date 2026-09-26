from btcintel.heuristics.base import Context
from btcintel.heuristics.cioh import cioh_addresses, cioh_heuristic
from tests import cj_samples as s
from tests.builders import mk_tx


async def test_ordinary_multi_input_links_addresses():
    tx = mk_tx([("a", 50_000), ("b", 60_000), ("a", 1_000)], [("c", 100_000)])
    assert cioh_addresses(tx) == ["a", "b"]
    (f,) = await cioh_heuristic(tx, Context())
    assert (f.label, f.evidence["addresses"]) == ("common_input", ["a", "b"])


async def test_coinjoin_suppresses_cioh():
    tx = s.whirlpool_mix()
    assert cioh_addresses(tx) is None
    (f,) = await cioh_heuristic(tx, Context())
    assert f.label == "cioh_suppressed" and f.evidence["reason"] == "coinjoin:whirlpool"


async def test_tx0_keeps_cioh():
    assert cioh_addresses(s.whirlpool_tx0(n_inputs=2)) is not None


async def test_single_address_and_coinbase():
    assert cioh_addresses(mk_tx([("a", 1), ("a", 2)], [("b", 2)])) is None
    assert await cioh_heuristic(mk_tx([("a", 1)], [("b", 1)]), Context()) == []
    assert await cioh_heuristic(mk_tx([(None, 0)], [("m", 1)], coinbase=True), Context()) == []
