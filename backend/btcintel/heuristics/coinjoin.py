"""H-CJ: CoinJoin detection (Whirlpool mix/Tx0, WabiSabi, ZeroLink, JoinMarket, Stonewall, generic).

Thresholds were calibrated on 2026-09-25 against crocs-muni/coinjoin-analysis ground truth
(coordinator txid lists and Dumplings scanner output).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject
from btcintel.heuristics.script import is_printable_ascii, op_return_payloads

WHIRLPOOL_POOLS = (100_000, 1_000_000, 2_500_000, 5_000_000, 25_000_000, 50_000_000)
SEGWIT_TYPES = frozenset({"v0_p2wpkh", "v1_p2tr"})
KIND_IDS = {
    "whirlpool": "H-CJ-WHIRLPOOL", "whirlpool_tx0": "H-CJ-WHIRLPOOL-TX0", "wasabi2": "H-CJ-WASABI2",
    "wasabi1": "H-CJ-WASABI1", "joinmarket": "H-CJ-JOINMARKET", "stonewall": "H-CJ-STONEWALL",
    "generic": "H-CJ-GENERIC",
}
CONFIDENCE = {
    "whirlpool": 0.95, "whirlpool_tx0": 0.9, "wasabi2": 0.9, "wasabi1": 0.9, "joinmarket": 0.6,
    "stonewall": 0.4, "generic": 0.3,
}
MULTIPARTY_KINDS = frozenset(KIND_IDS) - {"whirlpool_tx0"}
STRONG_KINDS = frozenset({"wasabi1", "wasabi2", "whirlpool", "whirlpool_tx0", "joinmarket"})


def _standard_denominations() -> frozenset[int]:
    """WabiSabi standard denominations: 2^n, 3^n, 2·3^n, 10^n, 2·10^n, 5·10^n sats (≥ 5000)."""
    values: set[int] = set()
    limit = 10**14
    for base in (2, 3, 10):
        v = 1
        while v <= limit:
            values.add(v)
            v *= base
    v = 1
    while v <= limit:
        values.update((2 * v, 5 * v))
        v *= 10
    v = 1
    while v <= limit:
        values.add(2 * v)
        v *= 3
    return frozenset(x for x in values if x >= 5_000)


STANDARD_DENOMINATIONS = _standard_denominations()


@dataclass(frozen=True)
class CoinJoinMatch:
    kind: str
    heuristic_id: str
    confidence: float
    denomination: int | None
    anonset: int
    equal_groups: int


def _mix_input(value: int, pool: int) -> bool:
    return pool <= value <= pool * 1.1 + 20_000


def _premix(value: int, pool: int) -> bool:
    return pool < value <= pool * 1.1 + 20_000


def classify_coinjoin(tx: Tx) -> CoinJoinMatch | None:
    if tx.is_coinbase or not tx.vin:
        return None
    outs = tx.spendable_outputs()
    if not outs:
        return None
    n_opret = len(tx.vout) - len(outs)
    n_in, n_out = len(tx.vin), len(outs)
    values = [o.value for o in outs]
    counts = Counter(values)
    denom, anonset = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    groups = sum(1 for c in counts.values() if c >= 2)
    in_types = {i.script_type for i in tx.vin}
    out_types = {o.script_type for o in outs}

    def match(kind: str, denomination: int | None, size: int) -> CoinJoinMatch:
        return CoinJoinMatch(kind, KIND_IDS[kind], CONFIDENCE[kind], denomination, size, groups)

    if (n_opret == 0 and n_in == n_out and 5 <= n_in <= 10 and anonset == n_out
            and denom in WHIRLPOOL_POOLS and all(_mix_input(i.value, denom) for i in tx.vin)):
        return match("whirlpool", denom, anonset)
    payloads = op_return_payloads(tx)
    if (n_opret == 1 and len(payloads) == 1 and len(payloads[0]) >= 40
            and not is_printable_ascii(payloads[0]) and out_types == {"v0_p2wpkh"}):
        for pool in WHIRLPOOL_POOLS:
            premix = [v for v in values if _premix(v, pool)]
            if premix and len(set(premix)) == 1:
                return match("whirlpool_tx0", pool, len(premix))
    std_share = sum(v in STANDARD_DENOMINATIONS for v in values) / n_out
    if (n_in >= 5 and in_types <= SEGWIT_TYPES and out_types <= SEGWIT_TYPES and tx.version == 1
            and tx.locktime == 0 and std_share >= 0.75 and groups >= 1):
        return match("wasabi2", denom, anonset)
    if (anonset >= 10 and 7_000_000 <= denom <= 13_000_000
            and in_types == {"v0_p2wpkh"} and out_types == {"v0_p2wpkh"}):
        return match("wasabi1", denom, anonset)
    # Dumplings' guard for equal-output CoinJoins: fewer distinct input addresses than equal outputs
    # means one actor (e.g. an exchange batch payout), not several participants.
    if len(set(tx.input_addresses())) < anonset:
        return None
    if anonset >= 3 and n_in >= anonset and n_out <= 2 * anonset + 1 and n_opret == 0:
        return match("joinmarket", denom, anonset)
    if n_out == 4 and anonset == 2 and groups == 1 and n_in >= 2:
        return match("stonewall", denom, anonset)
    # Each participant receives at most one equal output and one change output (+1 for a fee output);
    # far more outputs than that is a batch payout that happens to repeat an amount.
    equal_outputs = sum(c for c in counts.values() if c >= 2)
    if anonset >= 2 and n_in >= 2 and n_out <= 2 * equal_outputs + 1:
        return match("generic", denom, anonset)
    return None


def is_multiparty(tx: Tx) -> bool:
    m = classify_coinjoin(tx)
    return m is not None and m.kind in MULTIPARTY_KINDS


@heuristic("H-CJ")
async def coinjoin_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    m = classify_coinjoin(tx)
    if m is None:
        return []
    return [Finding(heuristic="H-CJ", subject=tx_subject(tx.txid), label=f"coinjoin:{m.kind}",
                    confidence=m.confidence,
                    evidence={**asdict(m), "multiparty": m.kind in MULTIPARTY_KINDS})]
