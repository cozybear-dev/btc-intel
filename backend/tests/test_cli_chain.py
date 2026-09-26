import json
from pathlib import Path

import httpx
import pytest

from btcintel.cli import main

FIX = Path(__file__).resolve().parent / "fixtures" / "esplora"
TXID = "c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c"


@pytest.mark.respx(assert_all_called=False)
def test_tx_command_prints_findings(tmp_path, monkeypatch, capsys, respx_mock):
    monkeypatch.setenv("BTCINTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BTCINTEL_BACKENDS", "t=https://esplora.test/api@100")
    respx_mock.get("https://esplora.test/api/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    respx_mock.get(f"https://esplora.test/api/tx/{TXID}").mock(
        return_value=httpx.Response(200, json=json.loads((FIX / "tx_c5908e04.json").read_text())))
    assert main(["tx", TXID]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["txid"] == TXID and any(f["heuristic"] == "H-FP" for f in out["findings"])


def test_tx_command_rejects_bad_txid(capsys):
    assert main(["tx", "nope"]) == 2
