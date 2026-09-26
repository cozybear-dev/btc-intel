import json
from pathlib import Path

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.base import Context
from btcintel.heuristics.fingerprint import fingerprint, fingerprint_heuristic
from tests.builders import mk_tx

A = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
B = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"


def der_sig(high_r: bool) -> str:
    r = (b"\x00\x80" + b"\x11" * 31) if high_r else b"\x11" * 32
    s = b"\x22" * 32
    body = b"\x02" + bytes([len(r)]) + r + b"\x02" + bytes([len(s)]) + s
    return (b"\x30" + bytes([len(body)]) + body + b"\x01").hex()


PUB = "02" + "33" * 32
UNCOMPRESSED = "04" + "44" * 64


def test_locktime_kinds_and_anti_fee_sniping():
    zero = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=0, height=900_000))
    assert zero.locktime_kind == "zero" and zero.anti_fee_sniping is False
    afs = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=899_990, height=900_000))
    assert afs.locktime_kind == "height" and afs.anti_fee_sniping is True
    old = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=850_000, height=900_000))
    assert old.anti_fee_sniping is False
    unconf = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=899_990, confirmed=False))
    assert unconf.anti_fee_sniping is None
    timed = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=1_700_000_000))
    assert timed.locktime_kind == "time"


def test_rbf_and_sequences():
    fp = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], sequence=0xFFFFFFFD))
    assert fp.rbf and fp.sequences == ("fffffffd",)
    assert not fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], sequence=0xFFFFFFFE)).rbf


def test_bip69():
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)])).bip69 is None
    sorted_outs = fingerprint(mk_tx([(A, 10_000)], [(B, 1_000), (A, 8_000)]))
    unsorted = fingerprint(mk_tx([(A, 10_000)], [(B, 8_000), (A, 1_000)]))
    assert sorted_outs.bip69 is True and unsorted.bip69 is False


def test_signatures_and_pubkeys():
    low = fingerprint(mk_tx([(A, 10_000), (B, 5_000)], [(B, 14_000)],
                            witness=[[der_sig(False), PUB], [der_sig(False), PUB]]))
    assert (low.ecdsa_sigs, low.high_r_sigs, low.low_r_only) == (2, 0, True)
    mixed = fingerprint(mk_tx([(A, 10_000), (B, 5_000)], [(B, 14_000)],
                              witness=[[der_sig(False), PUB], [der_sig(True), UNCOMPRESSED]]))
    assert mixed.low_r_only is False and mixed.uncompressed_pubkey
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)])).low_r_only is None


def test_feerate_integer():
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], fee=1_000)).feerate_int is True  # vsize 250
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], fee=1_001)).feerate_int is False


def test_signature_ignores_shape_dependent_traits():
    a = fingerprint(mk_tx([(A, 10_000)], [(B, 1_000), (A, 8_000)]))
    b = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)]))
    assert a.bip69 != b.bip69 and a.signature() == b.signature()
    c = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], version=1))
    assert c.signature() != b.signature()


def test_real_transaction_fingerprint():
    tx = parse_tx(json.loads((FIX / "tx_c5908e04.json").read_text()))
    fp = fingerprint(tx)
    assert fp.version == 2 and fp.locktime_kind == "zero" and not fp.rbf
    assert "p2pkh" in fp.input_types and fp.ecdsa_sigs >= 1


async def test_heuristic_emits_finding_and_skips_coinbase():
    tx = mk_tx([(A, 10_000)], [(B, 9_000)])
    (f,) = await fingerprint_heuristic(tx, Context())
    assert f.heuristic == "H-FP" and f.label == "fingerprint" and f.evidence["version"] == 2
    assert "signature" in f.evidence
    coinbase = mk_tx([(None, 0)], [(B, 312_500_000)], coinbase=True)
    assert await fingerprint_heuristic(coinbase, Context()) == []
