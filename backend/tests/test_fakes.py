import pytest

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import NotFound, SourceError
from tests.builders import mk_tx
from tests.fakes import FakeChain

A1 = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
A2 = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"


async def test_fake_chain_derives_outspends_and_history():
    parent = mk_tx([(A1, 100_000, "p2pkh")], [(A2, 60_000), (A1, 39_000, "p2pkh")])
    child = mk_tx([(parent, 0)], [(A1, 59_000, "p2pkh")])
    chain = FakeChain([parent, child])
    spends = await chain.get_outspends(parent.txid)
    assert spends[0].spent and spends[0].txid == child.txid and spends[0].vin == 0
    assert not spends[1].spent
    assert [t.txid async for t in chain.iter_address_txs(A2)] == [parent.txid, child.txid]
    stats = await chain.get_address(A2)
    assert stats.funded_sum == 60_000 and stats.spent_sum == 60_000 and stats.tx_count == 2


async def test_fake_chain_errors_and_budget():
    tx = mk_tx([(A1, 1000, "p2pkh")], [(A2, 900)])
    chain = FakeChain([tx], fail_on={tx.txid})
    with pytest.raises(SourceError):
        await chain.get_tx(tx.txid)
    with pytest.raises(NotFound):
        await chain.get_tx("ff" * 32)
    with budget_scope(CallBudget(1)), pytest.raises(BudgetExceeded):
        await chain.tip_height()
        await chain.tip_height()
