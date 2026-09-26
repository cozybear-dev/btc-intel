from btcintel.heuristics.base import Context
from btcintel.heuristics.patterns import (
    fanin_heuristic,
    fanin_shape,
    fanout_heuristic,
    fanout_shape,
    peel_heuristic,
    peel_shape,
)
from tests import cj_samples as s
from tests.builders import mk_tx


async def test_peel_step():
    tx = mk_tx([("a", 10_000_000)], [("b", 500_000), ("c", 9_490_000)])
    assert peel_shape(tx) == {"remainder_output": 1, "peel_output": 0, "peel_value": 500_000,
                              "remainder_share": 0.95}
    (f,) = await peel_heuristic(tx, Context())
    assert f.label == "peel_step"
    assert peel_shape(mk_tx([("a", 10_000_000)], [("b", 5_000_000), ("c", 4_990_000)])) is None
    assert peel_shape(mk_tx([("a", 10_000_000)], [("b", 1), ("c", 2), ("d", 9_000_000)])) is None


async def test_fanout_uniform_vs_varied():
    uniform = mk_tx([("a", 2_000_000)], [(f"o{i}", 100_000) for i in range(12)])
    varied = mk_tx([("a", 9_000_000)], [(f"o{i}", 10_000 * (i + 1) ** 2) for i in range(12)])
    assert fanout_shape(uniform)["label"] == "dispersal_uniform"
    assert fanout_shape(varied)["label"] == "fan_out"
    assert fanout_shape(mk_tx([("a", 9_000)], [(f"o{i}", 1_000) for i in range(5)])) is None
    (f,) = await fanout_heuristic(uniform, Context())
    assert f.heuristic == "H-MOTIF-FANOUT" and f.confidence == 0.6


async def test_fanin_consolidation_excludes_coinjoin():
    tx = mk_tx([(f"i{i}", 10_000) for i in range(12)], [("z", 110_000)])
    assert fanin_shape(tx) == {"n_in": 12, "distinct_input_addresses": 12}
    (f,) = await fanin_heuristic(tx, Context())
    assert f.label == "consolidation"
    assert fanin_shape(s.wasabi1_round()) is None
