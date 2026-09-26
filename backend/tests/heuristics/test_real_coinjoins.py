import json
from pathlib import Path

import pytest

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.cioh import cioh_addresses
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, STRONG_KINDS, classify_coinjoin

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "real"
MANIFEST = FIX / "manifest.json"
pytestmark = pytest.mark.skipif(not MANIFEST.exists(), reason="run scripts/record_fixtures.py first")


def load(kind: str):
    entries = json.loads(MANIFEST.read_text())[kind]
    return [parse_tx(json.loads((FIX / kind / f"{e['txid']}.json").read_text())) for e in entries]


def kinds(kind: str) -> list[str | None]:
    return [(m.kind if (m := classify_coinjoin(tx)) else None) for tx in load(kind)]


def test_wasabi2_rounds_suppress_cioh_and_are_mostly_identified():
    got = kinds("wasabi2")
    assert all(k in MULTIPARTY_KINDS for k in got), got
    assert got.count("wasabi2") >= 0.8 * len(got), got


@pytest.mark.parametrize("kind", ["whirlpool", "whirlpool_tx0", "wasabi1"])
def test_exact_kinds(kind):
    got = kinds(kind)
    assert got and all(k == kind for k in got), got


def test_tx0s_keep_cioh():
    assert all(cioh_addresses(tx) is not None or len(tx.input_addresses()) < 2 for tx in load("whirlpool_tx0"))


def test_other_coinjoins_are_flagged():
    assert all(k is not None for k in kinds("other_coinjoin"))


def test_ordinary_transactions_are_not_strong_coinjoins():
    got = kinds("ordinary")
    assert not [k for k in got if k in STRONG_KINDS], got
    assert sum(k is not None for k in got) <= 3, got


def test_service_batch_payouts_are_not_coinjoins():
    got = kinds("batch_payout")
    assert len(got) == 4 and got == [None] * 4, got
