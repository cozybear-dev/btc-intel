import json
from pathlib import Path

from btcintel.chain.esplora_parse import parse_address, parse_outspends, parse_tx
from tests.builders import mk_tx

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"
TXID = "c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c"


def load(name: str):
    return json.loads((FIX / name).read_text())


def test_parse_regular_tx():
    tx = parse_tx(load("tx_c5908e04.json"))
    assert (tx.txid, tx.version, tx.locktime) == (TXID, 2, 0)
    assert tx.status.confirmed and tx.status.block_height == 900000
    first = tx.vin[0]
    assert first.prev_txid == "0b027a1d8e16f279eb2bce977536db83e5e0570145921262ad7c21f5524eaad6"
    assert first.prev_vout == 5 and first.n == 0
    assert first.value == 44855514
    assert first.address == "1AXeFwAnsd1BkvBwPumsNnjzp4sAEUwyMX"
    assert first.script_type == "p2pkh" and first.sequence == 0xFFFFFFFF
    out0 = tx.vout[0]
    assert (out0.value, out0.address, out0.script_type) == (
        10000, "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6", "v0_p2wpkh",
    )
    assert [o.n for o in tx.vout] == list(range(len(tx.vout)))
    assert tx.fee == tx.input_value - tx.output_value > 0
    assert tx.vsize == (tx.weight + 3) // 4 and not tx.is_coinbase


def test_parse_coinbase():
    tx = parse_tx(load("tx_coinbase_900000.json"))
    assert tx.is_coinbase and tx.vin[0].prevout is None and tx.vin[0].value == 0
    assert b"/ViaBTC/" in bytes.fromhex(tx.vin[0].scriptsig_hex)
    assert tx.fee == 0


def test_parse_outspends():
    spends = parse_outspends(load("outspends_c5908e04.json"))
    assert spends[0].spent and spends[0].vin == 26
    assert spends[0].txid == "29fd5eabd31534fdc4d861a27a8fb1f6019654d0d17e0f6dc32c3c214ac060a0"
    assert spends[0].status.confirmed and spends[0].status.block_height == 911650


def test_parse_address():
    st = parse_address(load("address_genesis.json"))
    assert st.address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
    assert st.spent_sum == 0 and st.balance == st.funded_sum and st.tx_count > 60000


def test_model_dump_includes_computed_fields():
    d = parse_tx(load("tx_c5908e04.json")).model_dump()
    assert {"is_coinbase", "input_value", "output_value", "vsize", "feerate"} <= d.keys()


def test_builder_makes_consistent_transactions():
    parent = mk_tx(
        [("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 100_000, "p2pkh")],
        [("bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6", 90_000)],
        op_returns=[b"hello"],
    )
    assert parent.fee == 10_000
    assert parent.vout[-1].script_type == "op_return"
    assert parent.vout[-1].script_hex == "6a0568656c6c6f"
    child = mk_tx([(parent, 0)], [("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 89_000)])
    assert child.vin[0].prev_txid == parent.txid and child.vin[0].prev_vout == 0
    assert child.vin[0].value == 90_000 and child.fee == 1_000
    assert parent.txid != child.txid
