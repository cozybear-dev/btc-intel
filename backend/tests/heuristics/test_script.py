from btcintel.chain.models import TxOut
from btcintel.heuristics.script import is_printable_ascii, op_return_payloads
from tests.builders import mk_tx


def _tx_with_scripts(*scripts: str):
    tx = mk_tx([("a", 1000)], [("b", 900)])
    outs = list(tx.vout) + [TxOut(n=len(tx.vout) + i, value=0, script_type="op_return", script_hex=s)
                            for i, s in enumerate(scripts)]
    return tx.model_copy(update={"vout": outs})


def test_payload_extraction():
    tx = _tx_with_scripts("6a0568656c6c6f", "6a4c50" + "ab" * 80, "6a01610162", "6a0568", "zz")
    assert op_return_payloads(tx) == [b"hello", b"\xab" * 80, b"ab", b"h"]


def test_printable_ascii():
    assert is_printable_ascii(b"=:ETH.ETH:0xabc")
    assert not is_printable_ascii(bytes(range(64))) and not is_printable_ascii(b"")
