"""Profile of an address from its stats and fetched history: activity, behaviour, wallet fingerprint."""

from __future__ import annotations

from collections import Counter
from itertools import pairwise
from typing import Any

from btcintel.analysis.models import FingerprintSummary, Profile
from btcintel.chain.models import AddressStats, Tx
from btcintel.chain.validate import address_type
from btcintel.heuristics.fingerprint import fingerprint
from btcintel.heuristics.flags import tx_flags

DAY = 86_400


def summarize_fingerprints(signed: list[Tx]) -> FingerprintSummary:
    """The dominant wallet fingerprint among transactions the address signed, and how consistent it is."""
    prints = [fingerprint(t) for t in signed if not t.is_coinbase]
    if not prints:
        return FingerprintSummary(signed_txs=0)
    signature, n = Counter(p.signature() for p in prints).most_common(1)[0]
    ex = next(p for p in prints if p.signature() == signature)
    traits = {
        "version": ex.version,
        "locktime": ex.locktime_kind,
        "anti_fee_sniping": ex.anti_fee_sniping,
        "rbf": ex.rbf,
        "low_r_only": ex.low_r_only,
        "bip69": ex.bip69,
        "input_types": list(ex.input_types),
    }
    return FingerprintSummary(
        signed_txs=len(prints),
        signature=signature,
        share=round(n / len(prints), 3),
        traits=traits,
    )


def build_profile(
    address: str, stats: AddressStats, history: list[Tx], info: dict[str, Any]
) -> Profile:
    signed = [t for t in history if address in t.input_addresses()]
    received = [t for t in history if address in t.output_addresses()]
    external = sum(
        o.value
        for t in received
        if address not in t.input_addresses()
        for o in t.vout
        if o.address == address
    )
    times = sorted(t.status.block_time for t in history if t.status.block_time)
    gaps = [b - a for a, b in pairwise(times)]
    behaviour = Counter(flag for t in history for flag in tx_flags(t))
    return Profile(
        address=address,
        address_type=address_type(address),
        stats=stats,
        info=info,
        txs_seen=len(history),
        history_complete=len(history) >= stats.tx_count,
        first_seen=times[0] if times else None,
        last_seen=times[-1] if times else None,
        longest_gap_days=round(max(gaps) / DAY, 1) if gaps else None,
        received_txs=len(received),
        sent_txs=len(signed),
        received_external=external,
        reused=stats.funded_txo_count > 1,
        behaviour=dict(sorted(behaviour.items())),
        fingerprint=summarize_fingerprints(signed),
    )
