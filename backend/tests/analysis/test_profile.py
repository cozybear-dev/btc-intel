from btcintel.analysis.profile import build_profile
from btcintel.chain.models import AddressStats, TxStatus
from tests.builders import ADDR, mk_tx

A, X, Y = ADDR[1], ADDR[9], ADDR[10]
DAY = 86_400
T0 = 1_600_000_000


def at(tx, ts):
    return tx.model_copy(
        update={"status": TxStatus(confirmed=True, block_height=800_000, block_time=ts)}
    )


def stats(**kw):
    base = {
        "address": A,
        "tx_count": 3,
        "funded_txo_count": 2,
        "funded_sum": 900_000,
        "spent_txo_count": 1,
        "spent_sum": 400_000,
    }
    return AddressStats(**{**base, **kw})


def history():
    r1 = at(mk_tx([(X, 500_000)], [(A, 400_000), (X, 99_000)]), T0)
    s1 = at(
        mk_tx([(A, 400_000)], [(Y, 300_000), (A, 99_000)], locktime=799_990),
        T0 + 10 * DAY,
    )
    r2 = at(mk_tx([(Y, 600_000)], [(A, 500_000)]), T0 + 400 * DAY)
    return [r2, s1, r1]  # newest first, as Esplora returns


def test_profile_activity_and_amounts():
    p = build_profile(A, stats(), history(), {"address": A, "tags": [], "risk": "none"})
    assert p.address_type == "v0_p2wpkh"
    assert (p.txs_seen, p.history_complete) == (3, True)
    assert (p.first_seen, p.last_seen) == (T0, T0 + 400 * DAY)
    assert p.longest_gap_days == 390.0
    assert (p.received_txs, p.sent_txs) == (3, 1)
    assert p.received_external == 900_000  # the 99k change back to A is not new money
    assert p.reused


def test_profile_fingerprint_of_signed_transactions():
    fp = build_profile(A, stats(), history(), {}).fingerprint
    assert fp.signed_txs == 1 and fp.share == 1.0
    assert fp.signature == "v2|lt:height|rbf:1|in:v0_p2wpkh"
    assert fp.traits["anti_fee_sniping"] is True and fp.traits["rbf"] is True


def test_profile_counts_behaviour_flags():
    mined = at(mk_tx([(None, 0)], [(A, 312_500_000)], coinbase=True), T0 - DAY)
    p = build_profile(A, stats(), [*history(), mined], {})
    assert p.behaviour.get("coinbase") == 1
    assert p.fingerprint.signed_txs == 1  # coinbase txs are never signed by the address


def test_profile_of_an_unused_address_and_a_truncated_history():
    empty = build_profile(
        A, stats(tx_count=0, funded_txo_count=0, funded_sum=0, spent_txo_count=0,
                  spent_sum=0), [], {}
    )
    assert (
        empty.first_seen is None
        and empty.longest_gap_days is None
        and empty.received_external == 0
    )
    assert (
        empty.fingerprint.signed_txs == 0
        and empty.history_complete
        and not empty.reused
    )
    assert not build_profile(A, stats(tx_count=50), history(), {}).history_complete
