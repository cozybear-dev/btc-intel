import json
from pathlib import Path

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.base import Context
from btcintel.heuristics.coinbase import coinbase_heuristic, match_pool
from tests.builders import mk_tx

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"
COINBASE = parse_tx(json.loads((FIX / "tx_coinbase_900000.json").read_text()))


async def test_known_pool():
    (f,) = await coinbase_heuristic(COINBASE, Context(coinbase_rules=[("/ViaBTC/", "ViaBTC")]))
    assert f.label == "miner:ViaBTC" and f.evidence["pool"] == "ViaBTC"


async def test_unknown_pool_keeps_text():
    (f,) = await coinbase_heuristic(COINBASE, Context())
    assert f.label == "miner:unknown" and "ViaBTC" in f.evidence["coinbase_text"]


async def test_non_coinbase_ignored():
    assert await coinbase_heuristic(mk_tx([("a", 1)], [("b", 1)]), Context()) == []


def test_match_pool_uses_rule_order():
    hexed = b"xx/F2Pool/xyz/yy".hex()
    assert match_pool(hexed, [("/F2Pool/xyz/", "Other"), ("/F2Pool/", "F2Pool")]) == "Other"
    assert match_pool(hexed, []) is None
