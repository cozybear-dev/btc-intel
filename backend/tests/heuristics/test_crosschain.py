import pytest

from btcintel.heuristics.base import Context
from btcintel.heuristics.crosschain import (
    crosschain_heuristic,
    parse_thorchain_memo,
    xchain_markers,
)
from tests import cj_samples as s
from tests.builders import mk_tx

H = "a" * 64


@pytest.mark.parametrize("memo,action,asset,dest,inbound", [
    ("=:ETH.ETH:0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0", "swap", "ETH.ETH",
     "0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0", None),
    ("SWAP:BTC.BTC:bc1qxyz:0/1/0", "swap", "BTC.BTC", "bc1qxyz", None),
    ("s:eth.usdt-0xdac17f958d2ee523a2206206994597c13d831ec7:0xabc", "swap",
     "ETH.USDT-0XDAC17F958D2EE523A2206206994597C13D831EC7", "0xabc", None),
    ("+:BTC.BTC", "add", "BTC.BTC", None, None),
    ("WITHDRAW:BTC/BTC:10000", "withdraw", "BTC/BTC", None, None),
    ("d:ETH.ETH", "donate", "ETH.ETH", None, None),
    (f"OUT:{H}", "outbound", None, None, H),
    (f"REFUND:{H}", "refund", None, None, H),
])
def test_memo_grammar(memo, action, asset, dest, inbound):
    m = parse_thorchain_memo(memo)
    assert (m.action, m.asset, m.destination, m.inbound_hash) == (action, asset, dest, inbound)


@pytest.mark.parametrize("text", ["hello world", "=:notanasset:addr", "OUT:xyz", "", "SWAP"])
def test_non_memos(text):
    assert parse_thorchain_memo(text) is None


async def test_heuristic_on_thorchain_and_omni():
    (f,) = await crosschain_heuristic(s.thorchain_swap(), Context())
    assert f.label == "thorchain:swap" and f.evidence["destination"].startswith("0xe6a3")
    omni = mk_tx([("a", 10_000)], [("b", 546)], op_returns=[b"omni" + bytes(16)])
    assert [m[0] for m in xchain_markers(omni)] == ["omni_layer"]
    assert xchain_markers(s.whirlpool_tx0()) == []
