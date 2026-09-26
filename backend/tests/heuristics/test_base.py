import pytest

from btcintel.chain.errors import SourceError
from btcintel.heuristics.base import (
    Context,
    Finding,
    analyze_tx,
    heuristic,
    out_subject,
    tx_subject,
)
from tests.builders import mk_tx

A = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"


def test_subjects():
    assert tx_subject("ab") == "tx:ab" and out_subject("ab", 2) == "out:ab:2"


def test_finding_confidence_bounds():
    with pytest.raises(ValueError):
        Finding(heuristic="H-X", subject="tx:a", label="x", confidence=1.5)


async def test_analyze_tx_runs_given_heuristics_and_reports_incomplete():
    tx = mk_tx([(A, 1000, "p2pkh")], [(A, 900, "p2pkh")])

    async def ok(t, ctx):
        return [Finding(heuristic="H-OK", subject=tx_subject(t.txid), label="ok", confidence=1.0)]

    async def broken(t, ctx):
        raise SourceError("backend down")

    findings = await analyze_tx(tx, Context(), heuristics={"H-OK": ok, "H-BROKEN": broken})
    assert [(f.heuristic, f.label) for f in findings] == [("H-OK", "ok"), ("H-BROKEN", "incomplete")]
    assert findings[1].evidence["error"] == "backend down"
    only = await analyze_tx(tx, Context(), only={"H-OK"}, heuristics={"H-OK": ok, "H-BROKEN": broken})
    assert [f.heuristic for f in only] == ["H-OK"]


def test_duplicate_registration_rejected():
    @heuristic("H-TEST-DUP")
    async def one(tx, ctx):
        return []

    with pytest.raises(ValueError, match="duplicate"):
        @heuristic("H-TEST-DUP")
        async def two(tx, ctx):
            return []

    from btcintel.heuristics import base
    base._REGISTRY.pop("H-TEST-DUP")


async def test_context_without_chain_returns_none():
    ctx = Context()
    assert await ctx.outspends("ab" * 32) is None and await ctx.tx("ab" * 32) is None
