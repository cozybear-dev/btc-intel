"""Record real-mainnet regression fixtures from published ground truth (network; ~2 minutes).

Ground truth: crocs-muni/coinjoin-analysis (coordinator txid lists + Dumplings scanner output).
Negatives: the first 40 non-coinbase transactions of block 900000.
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

RAW = "https://raw.githubusercontent.com/crocs-muni/coinjoin-analysis/main"
API = "https://mempool.space/api"
OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "real"
BLOCK_900000 = "000000000000000000010538edbfd2d5b809a33dd83f284aeea41c6d0d96968a"
# Service batch payouts that a loose equal-output rule flags as CoinJoins (found by the Plan 2 Task 18
# Bitfinex backward trace): single-actor inputs, or far more outputs than participants could receive.
DOGFOOD_NEGATIVES = {
    "9ffe06deb111a2cc65bf0761c347790eda8473311c6ae3409e905f32526aa13d": "dogfood: June 2016 batch payout, 13 inputs from one address, 4 equal outputs",
    "147eca6c8ec3fc362ddfcba214f2f137cd34845a5a10a0a1282a0c03861b3af5": "dogfood: June 2016 batch payout, 18 inputs from 3 addresses, 13 equal outputs",
    "7ed5eaa4e14fd61556ca5171bc64865086d21221030204c31c768f65b7b75e33": "dogfood: June 2016 batch payout, 15 input addresses, 7 equal of 48 outputs",
    "4532476dc890a86a40ef4154d50745b315089fe54e0e761b70838526f8c76cb2": "dogfood: June 2016 batch payout, 15 input addresses, 11 equal of 50 outputs",
}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "btc-intel-fixtures/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def dumplings(archive: str, member: str) -> list[str]:
    z = zipfile.ZipFile(io.BytesIO(get(f"{RAW}/tests/fixtures/{archive}")))
    return sorted(line.split(":::")[0] for line in z.read(member).decode().splitlines() if line.strip())


def main() -> int:
    candidates: list[tuple[str, str, str]] = []  # (kind, txid, source)
    coords: dict[str, str] = {}
    for group in json.loads(get(f"{RAW}/data/wasabi2/txid_coord.json")).values():
        coords.update(group)
    for coord in ("kruw", "gingerwallet", "opencoordinator", "wasabicoordinator"):
        for txid in sorted(t for t, c in coords.items() if c == coord)[:3]:
            candidates.append(("wasabi2", txid, f"wasabi2/txid_coord.json:{coord}"))
    sw = "dumplings__sw_202403.zip"
    candidates += [("whirlpool", t, f"{sw}:SamouraiCoinJoins") for t in dumplings(sw, "Scanner/SamouraiCoinJoins.txt")[:4]]
    candidates += [("whirlpool_tx0", t, f"{sw}:SamouraiTx0s") for t in dumplings(sw, "Scanner/SamouraiTx0s.txt")[:15]]
    ww1 = "dumplings__ww1_202405.zip"
    candidates += [("wasabi1", t, f"{ww1}:WasabiCoinJoins") for t in dumplings(ww1, "Scanner/WasabiCoinJoins.txt")[:3]]
    jm = "dumplings__jm_202406.zip"
    candidates += [("other_coinjoin", t, f"{jm}:OtherCoinJoins") for t in dumplings(jm, "Scanner/OtherCoinJoins.txt")[:6]]
    candidates += [("batch_payout", t, DOGFOOD_NEGATIVES[t]) for t in sorted(DOGFOOD_NEGATIVES)]
    txids = json.loads(get(f"{API}/block/{BLOCK_900000}/txids"))
    candidates += [("ordinary", t, "block 900000") for t in txids[1:41]]

    manifest: dict[str, list[dict[str, str]]] = {}
    for kind, txid, source in candidates:
        if kind == "whirlpool_tx0" and len(manifest.get(kind, [])) >= 4:
            continue
        raw = json.loads(get(f"{API}/tx/{txid}"))
        time.sleep(1.0)
        # Dumplings' Tx0 list also contains non-Tx0 transactions (checked 2026-09-25): keep real Tx0s only.
        if kind == "whirlpool_tx0" and sum(o["scriptpubkey_type"] == "op_return" for o in raw["vout"]) != 1:
            continue
        path = OUT / kind / f"{txid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw, indent=1))
        manifest.setdefault(kind, []).append({"txid": txid, "source": source})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print({k: len(v) for k, v in manifest.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
