import pytest

from btcintel.heuristics.base import Context
from btcintel.heuristics.coinjoin import (
    MULTIPARTY_KINDS,
    STANDARD_DENOMINATIONS,
    classify_coinjoin,
    coinjoin_heuristic,
    is_multiparty,
)
from tests import cj_samples as s
from tests.builders import mk_tx


@pytest.mark.parametrize("build,kind,denom,anonset", [
    (s.whirlpool_mix, "whirlpool", 1_000_000, 5),
    (s.ashigaru_remix, "whirlpool", 2_500_000, 6),
    (s.whirlpool_tx0, "whirlpool_tx0", 100_000, 5),
    (s.wasabi1_round, "wasabi1", 10_987_000, 50),
    (s.joinmarket_round, "joinmarket", 35_281_835, 5),
    (s.stonewall, "stonewall", 50_000, 2),
    (s.generic_equal, "generic", 40_000, 2),
])
def test_known_structures(build, kind, denom, anonset):
    m = classify_coinjoin(build())
    assert m is not None and (m.kind, m.denomination, m.anonset) == (kind, denom, anonset)
    assert m.heuristic_id.startswith("H-CJ-")


def test_wasabi2_requires_version_1():
    assert classify_coinjoin(s.wasabi2_round(version=1)).kind == "wasabi2"
    assert classify_coinjoin(s.wasabi2_round(version=2)).kind == "generic"


def test_thorchain_swap_is_not_a_tx0():
    assert classify_coinjoin(s.thorchain_swap()) is None


def test_ordinary_transactions():
    assert classify_coinjoin(mk_tx([("a", 100_000)], [("b", 60_000), ("c", 39_000)])) is None
    assert classify_coinjoin(mk_tx([("a", 50_000), ("b", 60_000)], [("c", 70_000), ("d", 39_000)])) is None
    assert classify_coinjoin(mk_tx([(None, 0)], [("m", 312_500_000)], coinbase=True)) is None


def test_single_actor_equal_outputs_are_not_coinjoins():
    """Dumplings' guard: distinct input addresses must cover the equal outputs (else one actor)."""
    one_owner = mk_tx([("hot", 4_000_000_000)] * 13,
                      [(f"p{i}", 20_000) for i in range(4)] + [(f"q{i}", 1_000_000 + i) for i in range(47)])
    assert classify_coinjoin(one_owner) is None
    three_owners = mk_tx([(f"hot{i % 3}", 4_000_000_000) for i in range(18)],
                         [(f"p{i}", 20_000) for i in range(13)] + [(f"q{i}", 1_000_000 + i) for i in range(36)])
    assert classify_coinjoin(three_owners) is None
    jm_shape_two_owners = mk_tx([(f"w{i % 2}", 40_000_000) for i in range(11)],
                                [(f"e{i}", 35_281_835) for i in range(5)] + [(f"c{i}", 1_000 + i) for i in range(4)])
    assert classify_coinjoin(jm_shape_two_owners) is None


def test_batch_payout_output_structure_is_not_a_coinjoin():
    """Each participant gets at most one equal output and one change output (+1 fee output)."""
    many_owners = mk_tx([(f"hot{i}", 4_000_000_000) for i in range(15)],
                        [(f"p{i}", 20_000) for i in range(7)] + [(f"q{i}", 1_000_000 + i) for i in range(41)])
    assert classify_coinjoin(many_owners) is None


def test_multiparty_excludes_tx0():
    assert "whirlpool_tx0" not in MULTIPARTY_KINDS
    assert is_multiparty(s.whirlpool_mix()) and not is_multiparty(s.whirlpool_tx0())


def test_standard_denominations():
    assert {5_000, 6_561, 13_122, 131_072, 200_000, 1_000_000} <= STANDARD_DENOMINATIONS
    assert 4_999 not in STANDARD_DENOMINATIONS and 1_024 not in STANDARD_DENOMINATIONS


async def test_heuristic_finding():
    (f,) = await coinjoin_heuristic(s.whirlpool_mix(), Context())
    assert f.heuristic == "H-CJ" and f.label == "coinjoin:whirlpool" and f.evidence["multiparty"]
    assert await coinjoin_heuristic(mk_tx([("a", 1000)], [("b", 900)]), Context()) == []
