import json
from pathlib import Path

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.flags import tx_flags
from tests import cj_samples as s
from tests.builders import mk_tx

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"


def test_flags():
    assert tx_flags(s.whirlpool_mix()) == ["coinjoin:whirlpool"]
    assert tx_flags(mk_tx([("a", 10_000_000)], [("b", 500_000), ("c", 9_490_000)])) == ["peel_step"]
    assert "thorchain:swap" in tx_flags(s.thorchain_swap())
    assert tx_flags(parse_tx(json.loads((FIX / "tx_coinbase_900000.json").read_text()))) == ["coinbase"]
    assert tx_flags(mk_tx([("a", 800_000)], [("b", 400_000), ("c", 399_000)])) == []
