from btcintel.labels.store import Tag
from btcintel.trace.peel import follow_peel_chain
from tests import cj_samples as s
from tests.builders import mk_tx
from tests.fakes import FakeChain
from tests.scenario import UNTAGGED, make_labels

a = UNTAGGED


def chain3():
    p0 = mk_tx([(a[0], 10_000_000)], [(a[1], 500_000), (a[2], 9_490_000)])
    p1 = mk_tx([(p0, 1)], [(a[3], 400_000), (a[4], 9_080_000)])
    p2 = mk_tx([(p1, 1)], [(a[5], 300_000), (a[6], 8_770_000)])
    return p0, p1, p2


async def test_follows_until_unspent():
    p0, p1, p2 = chain3()
    pc = await follow_peel_chain(p0.txid, FakeChain([p0, p1, p2]), make_labels())
    assert [st.txid for st in pc.steps] == [p0.txid, p1.txid, p2.txid]
    assert pc.end_reason == "unspent" and pc.end_txid == p2.txid
    assert pc.total_peeled == 1_200_000 and pc.steps[0].peels[0]["address"] == a[1]


async def test_stops_at_labeled_remainder():
    p0, p1, p2 = chain3()
    labels = make_labels([Tag(address=a[4], label="Exchange", category="exchange",
                              confidence="authority_data", source="t", pack="t")])
    pc = await follow_peel_chain(p0.txid, FakeChain([p0, p1, p2]), labels)
    assert pc.end_reason == "labeled" and len(pc.steps) == 2


async def test_not_peel_shaped_and_coinjoin():
    odd = mk_tx([(a[0], 1_000_000)], [(a[1], 500_000), (a[2], 499_000)])
    assert (await follow_peel_chain(odd.txid, FakeChain([odd]), make_labels())).end_reason == "not_peel_shaped"
    mix = s.whirlpool_mix()
    assert (await follow_peel_chain(mix.txid, FakeChain([mix]), make_labels())).end_reason == "coinjoin"
