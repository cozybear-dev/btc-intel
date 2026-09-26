# Automatic Address Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entering a BTC address runs one automatic analysis. It produces a risk verdict with reasons, where the funds came from and went to, a cluster and wallet profile, and a pre-built graph, all streamed live to a report page.

**Architecture:**
- A new backend package, `btcintel/analysis/`, chains existing pieces into one job on the existing `JobManager`, with SSE events:
  - profile: address stats plus history, labels, flags and fingerprint
  - a capped CIOH cluster expansion
  - a backward and a forward trace, run concurrently
  - exposure buckets and an explainable verdict
- The job is exposed through `POST /api/analyze` and `btcintel analyze`.
- The React workbench gets an `#/analysis/<address>` route that renders `section` events as they arrive. The same job's graph events feed the existing graph model.

**Tech Stack:**
- Backend: Python 3.13, FastAPI, pydantic v2, pytest (asyncio auto mode), ruff.
- Web: React 19, zustand, Tailwind v4, vitest with Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-26-address-analysis-design.md`

## Global Constraints

- Budgets, copied from the spec:
  - quick: history 100 txs; each trace 3 hops, 60 txs, 120 calls; cluster 200 addresses, 60 calls
  - deep: history 500 txs; each trace 6 hops, 300 txs, 600 calls; cluster 2000 addresses, 400 calls
- Both traces use `min_value_sats=10_000`, `taint_model="haircut"`, and `max_address_txs` equal to the history size.
- Analysis traces stop at every taxonomy category except `unknown`, and match a tag's `abuse` as well as its `category`.
- Verdict thresholds are named constants: 10% of traced value involving high/severe entities means high; 25% involving medium entities means medium; below 50% resolved coverage the verdict is flagged "low confidence".
- Default (non-analysis) traces keep their behavior. The only change is that `Stop` gains a `hops` field and address-seeded forward traces count the seed's own coins as hop 0, so the first recipient is hop 1. That matches backward traces, where the first payer is already hop 1.
- No new dependencies (backend or web), and no new server-side storage.
- Backend: run commands from `backend/` with `uv run …`; `uv run ruff check .` must pass (line length 100).
- Web: run commands from `web/`; `npm test`, `npm run typecheck` and `npm run e2e` must pass.
- Every commit message ends with the trailer line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the commands below pass it as a second `-m`).
- Work on branch `feat/address-analysis`, which already exists and holds the spec commit.

## Review Focus

1. **Analysing an address that is already labeled** (pasting a known ransomware or OFAC address is the most common use): the report must still show its sources and destinations, not stop at the address itself. Pinned by Task 1 `test_labeled_seed_address_does_not_stop_its_own_trace` and `test_labeled_seed_address_is_traced_back_through_its_own_older_coins`, and Task 5 `test_a_labeled_address_still_shows_where_its_funds_went`.
2. **An address that never received funds:** a complete report with verdict "none" and "No incoming funds", with no division by zero. Pinned by Task 3 `test_zero_total_and_incomplete_trace`, Task 5 `test_unused_address_gives_an_empty_but_complete_report` and Task 6 `test_markdown_for_an_unused_address`.
3. **One chain lookup failing mid-analysis** (a missing parent tx, or a backend down during one trace): that section says the trace failed and the rest of the report still completes. Pinned by Task 5 `test_a_failing_trace_direction_is_reported_not_fatal`.
4. **Upper- or mixed-case bech32 in the search box or URL:** normalized once, and "Open in graph" selects the lowercase node the backend produced. Pinned by Task 7 `test_analyze_job_streams_sections_and_returns_the_report` (posts `A.upper()`) and Task 9 `test("Open in graph uses the normalised address …")`.
5. **Starting another analysis while one runs** (Go deeper, or a new search) **or over unsaved work:** the previous job is cancelled, its late events are ignored, and a hand-built graph is only discarded after confirmation. Pinned by Task 8 `test("a new analysis asks before discarding a hand-built graph …")`.

---

## File Structure

**Backend (new):**

| File | Purpose |
|---|---|
| `backend/btcintel/analysis/__init__.py` | package docstring |
| `backend/btcintel/analysis/models.py` | pydantic models: `AnalysisPolicy`, `FingerprintSummary`, `Profile`, `ClusterSummary`, `Bucket`, `Exposure`, `Reason`, `Verdict`, `AnalysisReport` |
| `backend/btcintel/analysis/profile.py` | pure: `build_profile(address, stats, history, info)`, `summarize_fingerprints(signed)` |
| `backend/btcintel/analysis/exposure.py` | pure: `compute_exposure(direction, result, total, *, taxonomy, own_cluster)`, `failed_exposure(direction, total, error)` |
| `backend/btcintel/analysis/verdict.py` | pure: `build_verdict(...)`, plus the `btc()` and `pct()` formatters |
| `backend/btcintel/analysis/report.py` | `to_markdown(report)` |
| `backend/btcintel/analysis/run.py` | `analyze_address(...)`: orchestration and events |
| `backend/btcintel/api/routes_analysis.py` | `POST /api/analyze` |
| `backend/tests/analysis_scenario.py` | the funded test graph and `run_analysis()` helper |
| `backend/tests/analysis/test_profile.py`, `test_exposure.py`, `test_verdict.py`, `test_run.py`, `test_report.py` | tests |
| `backend/tests/api/test_analysis_api.py`, `backend/tests/test_cli_analyze.py` | tests |

**Backend (modified):**
- `backend/btcintel/labels/lookup.py`: abuse-aware stop matching; the riskiest match wins.
- `backend/btcintel/trace/graph.py`: adds `Stop.hops`.
- `backend/btcintel/trace/engine.py`: records hops, exempts the seed from label stops, and counts an address seed's own coins as hop 0.
- `backend/btcintel/api/app.py`: registers the router.
- `backend/btcintel/cli.py`: adds the `analyze` command.

**Web (new):**
- `web/src/components/AnalysisView.tsx` and `AnalysisView.test.tsx`

**Web (modified):**
- `web/src/api/types.ts`: analysis types, the `section` event, `Stop.hops`.
- `web/src/api/client.ts`: `analyze`.
- `web/src/lib/route.ts` (and test): the `analysis` route.
- `web/src/lib/format.ts` (and test): `formatPct`.
- `web/src/state/store.ts`: the `analysis` slice and the `"analysis"` job kind.
- `web/src/state/actions.ts` (and test): `startAnalysis`, `saveAnalysisAsCase`, `hasUnsavedWork`, section handling; address search navigates to the analysis page; `openAddress` is removed.
- `web/src/App.tsx` (and test): Analysis nav and view.
- `web/src/components/SearchBar.tsx` and `KbBrowser.tsx` (and tests): address targets open the analysis page.
- `web/src/test/fixtures.ts`: `analysisSections`.
- `web/e2e/fixtures.ts` and `workbench.spec.ts`
- `README.md`

---

### Task 1: Trace fixes: abuse-aware stops, `Stop.hops`, seed exemption

**Files:**
- Modify: `backend/btcintel/labels/lookup.py:62-68`
- Modify: `backend/btcintel/trace/graph.py:33-37` and `:128-132`
- Modify: `backend/btcintel/trace/engine.py:110-266` (`_forward` and `_backward`)
- Test: `backend/tests/labels/test_lookup.py`, `backend/tests/trace/test_engine.py`

**Interfaces:**
- Produces:
  - `Stop.hops: int | None`, the number of transactions between the seed and the endpoint (1 = direct counterparty).
  - `GraphBuilder.stop(node, reason, taint=0.0, detail="", hops=None)`.
  - `LabelLookup.lookup(a).stop_category`, which can now be an abuse id (e.g. `"ransomware"`) when the stop set contains it, and is the riskiest matching id.

- [ ] **Step 1: Write the failing lookup test.** Append to `backend/tests/labels/test_lookup.py`:

```python
def test_stop_matches_abuse_and_prefers_the_riskiest():
    tags = TagStore(open_intel_db(":memory:"))
    tags.add_many([
        Tag(address="rw", label="LockBit", category="unknown", abuse="ransomware", confidence="forensic",
            source="s", pack="p"),
        Tag(address="gx", label="Garantex", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="gx", label="Garantex (OFAC)", category="organization", abuse="sanctioned",
            confidence="forensic", source="s", pack="p"),
    ])
    default = LabelLookup(tags, TAX)
    assert default.lookup("rw").stop_category is None  # abuse ids are not default stop categories
    assert default.lookup("gx").stop_category == "exchange"
    everything = LabelLookup(tags, TAX, stop_categories=set(TAX.categories) - {"unknown"})
    assert everything.lookup("rw").stop_category == "ransomware"
    assert everything.lookup("gx").stop_category == "sanctioned"
```

- [ ] **Step 2: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/labels/test_lookup.py -v`
  - Expected: `test_stop_matches_abuse_and_prefers_the_riskiest` FAILS (`None == 'ransomware'`).

- [ ] **Step 3: Implement abuse-aware stops.** In `backend/btcintel/labels/lookup.py`, replace the line `stop = next((t.category for t in ordered if t.category in self.stop), None)` with:

```python
        # A tag stops a trace by its entity category or by its abuse (many risky tags are
        # category "unknown" + abuse "ransomware"); among several matches the riskiest wins, so a
        # sanctioned exchange stops as "sanctioned", not "exchange".
        matches = [c for t in ordered for c in (t.abuse, t.category) if c in self.stop]
        stop = max(matches, key=lambda c: RISK_ORDER[self.taxonomy.risk(c)], default=None)
```

- [ ] **Step 4: Run the lookup tests.**
  - Run: `cd backend && uv run pytest tests/labels/test_lookup.py -v`
  - Expected: all PASS.

- [ ] **Step 5: Write the failing engine tests.** Append to `backend/tests/trace/test_engine.py`:

```python
async def test_stops_record_hops_from_an_address_seed():
    sc = build_scenario()
    r = await trace(TraceSeed(address=H1), TracePolicy(), chain=FakeChain(sc.txs), labels=make_labels())
    hops = {(st.node, st.reason): st.hops for st in r.stops}
    assert hops[(f"addr:{EX}", "labeled")] == 1  # H1 pays EX directly
    assert hops[(f"addr:{U}", "unspent")] == 2   # H1 -> H3 -> U


async def test_labeled_seed_address_does_not_stop_its_own_trace():
    from btcintel.labels.store import Tag
    sc = build_scenario()
    labels = make_labels([Tag(address=H1, label="Known thief", category="perpetrator", abuse="theft",
                              confidence="forensic", source="t", pack="t")],
                         stop_categories=["perpetrator", "theft", "exchange", "mixing_service"])
    r = await trace(TraceSeed(address=H1), TracePolicy(), chain=FakeChain(sc.txs), labels=labels)
    assert (f"addr:{EX}", "labeled") in stops(r)
    assert not any(st.node == f"addr:{H1}" for st in r.stops)


async def test_labeled_seed_address_is_traced_back_through_its_own_older_coins():
    from btcintel.labels.store import Tag
    a = UNTAGGED
    seed = a[1]
    cb = mk_tx([(None, 0)], [(a[0], 1_000_000)], coinbase=True)
    fund = mk_tx([(cb, 0)], [(seed, 999_000)])
    spend = mk_tx([(fund, 0)], [(a[2], 500_000), (seed, 498_000)])
    labels = make_labels([Tag(address=seed, label="Known thief", category="perpetrator", abuse="theft",
                              confidence="forensic", source="t", pack="t")],
                         stop_categories=["perpetrator", "theft"])
    # FakeChain lists history in insertion order: with max_address_txs=1 only `spend` is seeded, so
    # its input (the seed's older coins from `fund`) is reached as an ordinary input.
    r = await trace(TraceSeed(address=seed), TracePolicy(direction="backward", max_address_txs=1, min_value_sats=1),
                    chain=FakeChain([cb, spend, fund]), labels=labels)
    assert not any(st.node == f"addr:{seed}" for st in r.stops)
    coinbase = next(st for st in r.stops if st.reason == "coinbase")
    assert coinbase.node == f"tx:{cb.txid}" and coinbase.hops == 3
```

- [ ] **Step 6: Run them and check they fail.**
  - Run: `cd backend && uv run pytest tests/trace/test_engine.py -v -k "hops or labeled_seed"`
  - Expected: all three FAIL. The first fails on the missing `hops` attribute; the other two fail because the seed is label-stopped at itself.

- [ ] **Step 7: Add `Stop.hops`.** In `backend/btcintel/trace/graph.py`, change `Stop` and `GraphBuilder.stop` to:

```python
class Stop(BaseModel):
    node: str
    reason: StopReason
    taint: float = 0.0
    detail: str = ""
    hops: int | None = None  # transactions between the seed and this endpoint (1 = direct counterparty)
```

```python
    def stop(self, node: str, reason: StopReason, taint: float = 0.0, detail: str = "",
             hops: int | None = None) -> None:
        stop = Stop(node=node, reason=reason, taint=round(taint, 2), detail=detail, hops=hops)
        self.stops.append(stop)
        if self.emit:
            self.emit({"type": "stop", "item": stop.model_dump()})
```

- [ ] **Step 8: Record hops and exempt the seed in the engine.** In `backend/btcintel/trace/engine.py`, replace the whole `_forward` and `_backward` functions (everything after `_is_stopping_coinjoin`) with:

```python
async def _forward(seed: TraceSeed, policy: TracePolicy, chain: ChainSource, labels: LabelLookup,
                   g: GraphBuilder) -> None:
    heap: list[tuple[float, int, int, str, int]] = []
    counter = itertools.count()
    poisoned: set[str] = set()
    # Outputs paying an address seed start at full value; taint reaching them again (e.g. the
    # address's own change) is already counted and must not be followed twice.
    seeded: set[tuple[str, int]] = set()

    def follow(tx: Tx, n: int, amount: float, hop: int) -> None:
        target = g.add_output(tx, n, amount)
        out = tx.vout[n]
        if out.address is None:
            return
        # A labeled seed address never stops its own trace: analysing a known address must still
        # show where its funds went.
        if out.address != seed.address:
            info = labels.lookup(out.address)
            if info.stop_category:
                g.stop(target, "labeled", amount, f"{info.stop_category}: {info.label}", hops=hop)
                return
        heapq.heappush(heap, (-amount, hop, next(counter), tx.txid, n))

    if seed.txid is not None:
        tx = await chain.get_tx(seed.txid)
        g.add_tx(tx)
        if seed.vout is not None and seed.vout >= len(tx.vout):
            raise ValueError(f"transaction has no output {seed.vout}")
        outs = [seed.vout] if seed.vout is not None else [o.n for o in tx.spendable_outputs()]
        for n in outs:
            follow(tx, n, float(tx.vout[n].value), 1)
    else:
        async with aclosing(chain.iter_address_txs(seed.address or "", policy.max_address_txs)) as txs:
            async for tx in txs:
                for out in tx.vout:
                    if out.address == seed.address:
                        g.add_tx(tx)
                        seeded.add((tx.txid, out.n))
                        # hop 0: the address's own coins, so whoever it pays is 1 hop away
                        # (as in backward traces, where whoever paid it is 1 hop away)
                        follow(tx, out.n, float(out.value), 0)

    while heap:
        neg, hop, _, txid, vout = heapq.heappop(heap)
        amount = -neg
        node = addr_node_id(g.txs[txid].vout[vout].address or "")
        if amount < policy.min_value_sats:
            g.stop(node, "min_value", amount, hops=hop)
            continue
        if hop > policy.max_hops:
            g.stop(node, "max_hops", amount, hops=hop)
            continue
        spends = await chain.get_outspends(txid)
        sp = spends[vout] if vout < len(spends) else None
        if sp is None or not sp.spent or sp.txid is None or sp.vin is None:
            g.stop(node, "unspent", amount, hops=hop)
            continue
        if sp.txid not in g.txs and len(g.txs) >= policy.max_txs:
            g.truncated = True
            g.stop(node, "max_txs", amount, hops=hop)
            continue
        child = await chain.get_tx(sp.txid)
        g.add_tx(child)
        g.add_input_taint(child, sp.vin, amount)
        cj_kind = _is_stopping_coinjoin(child, policy)
        if cj_kind:
            g.stop(tx_node_id(child.txid), "coinjoin", amount, cj_kind, hops=hop + 1)
            continue
        if policy.taint_model == "poison":
            if child.txid in poisoned:
                continue
            poisoned.add(child.txid)
        delta = taint_models.forward(policy.taint_model, child, {sp.vin: amount})
        targets = [(n, t) for n, t in sorted(delta.items()) if (child.txid, n) not in seeded]
        if policy.peel_mode:
            keep = remainder_output(child)
            for n, t in targets:
                if n != keep and t > 0:
                    g.stop(g.add_output(child, n, t), "peel_off", t, hops=hop + 1)
            targets = [(n, t) for n, t in targets if n == keep]
        for n, t in targets:
            if t > 0:
                follow(child, n, t, hop + 1)


async def _backward(seed: TraceSeed, policy: TracePolicy, chain: ChainSource, labels: LabelLookup,
                    g: GraphBuilder) -> None:
    heap: list[tuple[float, int, int, str, int]] = []
    counter = itertools.count()
    # Outputs paying an address seed are traced from their own seed; an input spending one (the
    # address funding its own change) would trace the same funding twice.
    seeded: set[tuple[str, int]] = set()

    def push(amount: float, hop: int, txid: str, vin: int) -> None:
        heapq.heappush(heap, (-amount, hop, next(counter), txid, vin))

    def seed_outputs(tx: Tx, tainted: dict[int, float]) -> None:
        g.add_tx(tx)
        for n, t in tainted.items():
            g.add_output(tx, n, t)
        if tx.is_coinbase:
            g.stop(tx_node_id(tx.txid), "coinbase", sum(tainted.values()), "newly mined coins", hops=1)
            return
        for i, t in sorted(taint_models.backward(policy.taint_model, tx, tainted).items()):
            if t > 0:
                push(t, 1, tx.txid, i)

    if seed.txid is not None:
        tx = await chain.get_tx(seed.txid)
        if seed.vout is not None:
            if seed.vout >= len(tx.vout):
                raise ValueError(f"transaction has no output {seed.vout}")
            seed_outputs(tx, {seed.vout: float(tx.vout[seed.vout].value)})
        elif tx.is_coinbase:
            seed_outputs(tx, {o.n: float(o.value) for o in tx.spendable_outputs()})
        else:
            g.add_tx(tx)
            for txin in tx.vin:
                push(float(txin.value), 1, tx.txid, txin.n)
    else:
        async with aclosing(chain.iter_address_txs(seed.address or "", policy.max_address_txs)) as txs:
            async for tx in txs:
                received = {o.n: float(o.value) for o in tx.vout if o.address == seed.address}
                if received:
                    seeded.update((tx.txid, n) for n in received)
                    seed_outputs(tx, received)

    while heap:
        neg, hop, _, txid, vin = heapq.heappop(heap)
        amount = -neg
        txin = g.txs[txid].vin[vin]
        if (txin.prev_txid, txin.prev_vout) in seeded:
            continue
        node = addr_node_id(txin.address) if txin.address else tx_node_id(txid)
        if amount < policy.min_value_sats:
            g.stop(node, "min_value", amount, hops=hop)
            continue
        if hop > policy.max_hops:
            g.stop(node, "max_hops", amount, hops=hop)
            continue
        # As forward: the seed address's own older coins are traced through, not a labeled stop.
        if txin.address and txin.address != seed.address:
            info = labels.lookup(txin.address)
            if info.stop_category:
                g.stop(node, "labeled", amount, f"{info.stop_category}: {info.label}", hops=hop)
                continue
        if txin.prev_txid not in g.txs and len(g.txs) >= policy.max_txs:
            g.truncated = True
            g.stop(node, "max_txs", amount, hops=hop)
            continue
        parent = await chain.get_tx(txin.prev_txid)
        g.add_tx(parent)
        g.add_output(parent, txin.prev_vout, amount)
        if parent.is_coinbase:
            g.stop(tx_node_id(parent.txid), "coinbase", amount, "newly mined coins", hops=hop + 1)
            continue
        cj_kind = _is_stopping_coinjoin(parent, policy)
        if cj_kind:
            g.stop(tx_node_id(parent.txid), "coinjoin", amount, cj_kind, hops=hop + 1)
            continue
        for i, t in sorted(taint_models.backward(policy.taint_model, parent, {txin.prev_vout: amount}).items()):
            if t > 0:
                push(t, hop + 1, parent.txid, i)
```

- [ ] **Step 9: Run the whole backend suite.** It proves default traces are unchanged.
  - Run: `cd backend && uv run pytest -q && uv run ruff check .`
  - Expected: all tests pass (276 previously, plus 4 new) and ruff is clean.

- [ ] **Step 10: Commit.**

```bash
git add backend/btcintel/labels/lookup.py backend/btcintel/trace/graph.py backend/btcintel/trace/engine.py \
  backend/tests/labels/test_lookup.py backend/tests/trace/test_engine.py
git commit -m "fix(trace): stop on abuse labels, record hops, never stop at a labeled seed" \
  -m "Address-seeded forward traces now count the seed's own coins as hop 0, so the first recipient is hop 1 like the first payer in backward traces." \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Analysis models and address profile

**Files:**
- Create: `backend/btcintel/analysis/__init__.py`
- Create: `backend/btcintel/analysis/models.py`
- Create: `backend/btcintel/analysis/profile.py`
- Test: `backend/tests/analysis/test_profile.py`

**Interfaces:**
- Consumes: `AddressStats` (`btcintel.chain.models`), `Tx`, `fingerprint()` (`btcintel.heuristics.fingerprint`), `tx_flags()` (`btcintel.heuristics.flags`), `address_type()` (`btcintel.chain.validate`), `Conflict` (`btcintel.cluster.expand`).
- Produces: every model below (later tasks import them from `btcintel.analysis.models`), plus `build_profile(address: str, stats: AddressStats, history: list[Tx], info: dict[str, Any]) -> Profile`.

- [ ] **Step 1: Create the package and models** (data definitions only; the tests in this and later tasks exercise them).

`backend/btcintel/analysis/__init__.py`:

```python
"""Automatic address analysis: profile, cluster, sources, destinations and an explained verdict."""
```

`backend/btcintel/analysis/models.py`:

```python
"""Data model of an automatic address analysis (profile, cluster, exposure, verdict, report)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from btcintel.catalog.schema import RiskLevel
from btcintel.chain.models import AddressStats
from btcintel.cluster.expand import Conflict

Depth = Literal["quick", "deep"]
Direction = Literal["backward", "forward"]
BucketKind = Literal["labeled", "own_cluster", "coinjoin", "unspent", "coinbase", "limits", "remainder"]


class AnalysisPolicy(BaseModel):
    depth: Depth
    history_txs: int
    trace_hops: int
    trace_txs: int
    trace_calls: int
    cluster_addresses: int
    cluster_calls: int
    min_value_sats: int = 10_000

    @classmethod
    def quick(cls) -> AnalysisPolicy:
        """About 300 API calls: 1-1.5 min on the public Esplora APIs."""
        return cls(depth="quick", history_txs=100, trace_hops=3, trace_txs=60, trace_calls=120,
                   cluster_addresses=200, cluster_calls=60)

    @classmethod
    def deep(cls) -> AnalysisPolicy:
        """About 1,600+ API calls: 5-10 min on the public Esplora APIs."""
        return cls(depth="deep", history_txs=500, trace_hops=6, trace_txs=300, trace_calls=600,
                   cluster_addresses=2000, cluster_calls=400)


class FingerprintSummary(BaseModel):
    signed_txs: int
    signature: str | None = None
    share: float = 0.0  # share of signed txs carrying the dominant signature
    traits: dict[str, Any] = {}


class Profile(BaseModel):
    address: str
    address_type: str | None
    stats: AddressStats
    info: dict[str, Any]  # AddressInfo.to_dict(): own + cluster-inherited tags, risk
    txs_seen: int
    history_complete: bool
    first_seen: int | None
    last_seen: int | None
    longest_gap_days: float | None
    received_txs: int
    sent_txs: int
    received_external: int  # received in txs the address did not fund itself: the traced total
    reused: bool
    behaviour: dict[str, int]  # tx flag -> count over the analysed history
    fingerprint: FingerprintSummary


class ClusterSummary(BaseModel):
    root: str
    size: int
    partial: bool
    capped: bool
    conflicts: list[Conflict] = []
    top_labels: list[dict[str, Any]] = []
    calls_used: int = 0
    error: str | None = None


class Bucket(BaseModel):
    kind: BucketKind
    key: str  # category/abuse id, coinjoin kind, or the stop reason
    label: str
    risk: RiskLevel = "none"
    source: str | None = None  # tag pack of the label
    amount: float = 0.0  # sats
    share: float = 0.0
    min_hops: int | None = None
    nodes: list[str] = []  # graph node ids of example endpoints


class Exposure(BaseModel):
    direction: Direction
    total: float
    buckets: list[Bucket]
    resolved_share: float
    incomplete: bool = False
    reason: str | None = None
    calls_used: int = 0
    error: str | None = None


class Reason(BaseModel):
    level: RiskLevel
    rule: str
    text: str


class Verdict(BaseModel):
    level: RiskLevel
    final: bool
    low_confidence: bool = False
    coverage: str
    reasons: list[Reason]


class AnalysisReport(BaseModel):
    address: str
    depth: Depth
    generated_at: float
    profile: Profile
    cluster: ClusterSummary | None
    sources: Exposure | None
    destinations: Exposure | None
    verdict: Verdict
    calls_used: int
    markdown: str = ""
```

- [ ] **Step 2: Write the failing profile tests.** Create `backend/tests/analysis/test_profile.py`:

```python
from btcintel.analysis.profile import build_profile
from btcintel.chain.models import AddressStats, TxStatus
from tests.builders import ADDR, mk_tx

A, X, Y = ADDR[1], ADDR[9], ADDR[10]
DAY = 86_400
T0 = 1_600_000_000


def at(tx, ts):
    return tx.model_copy(update={"status": TxStatus(confirmed=True, block_height=800_000, block_time=ts)})


def stats(**kw):
    base = {"address": A, "tx_count": 3, "funded_txo_count": 2, "funded_sum": 900_000,
            "spent_txo_count": 1, "spent_sum": 400_000}
    return AddressStats(**{**base, **kw})


def history():
    r1 = at(mk_tx([(X, 500_000)], [(A, 400_000), (X, 99_000)]), T0)
    s1 = at(mk_tx([(A, 400_000)], [(Y, 300_000), (A, 99_000)], locktime=799_990), T0 + 10 * DAY)
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
    empty = build_profile(A, stats(tx_count=0, funded_txo_count=0, funded_sum=0, spent_txo_count=0, spent_sum=0), [], {})
    assert empty.first_seen is None and empty.longest_gap_days is None and empty.received_external == 0
    assert empty.fingerprint.signed_txs == 0 and empty.history_complete and not empty.reused
    assert not build_profile(A, stats(tx_count=50), history(), {}).history_complete
```

- [ ] **Step 3: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/analysis/test_profile.py -v`
  - Expected: FAIL with `ModuleNotFoundError: No module named 'btcintel.analysis.profile'`.

- [ ] **Step 4: Implement the profile.** Create `backend/btcintel/analysis/profile.py`:

```python
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
    traits = {"version": ex.version, "locktime": ex.locktime_kind, "anti_fee_sniping": ex.anti_fee_sniping,
              "rbf": ex.rbf, "low_r_only": ex.low_r_only, "bip69": ex.bip69, "input_types": list(ex.input_types)}
    return FingerprintSummary(signed_txs=len(prints), signature=signature, share=round(n / len(prints), 3),
                              traits=traits)


def build_profile(address: str, stats: AddressStats, history: list[Tx], info: dict[str, Any]) -> Profile:
    signed = [t for t in history if address in t.input_addresses()]
    received = [t for t in history if address in t.output_addresses()]
    external = sum(o.value for t in received if address not in t.input_addresses()
                   for o in t.vout if o.address == address)
    times = sorted(t.status.block_time for t in history if t.status.block_time)
    gaps = [b - a for a, b in pairwise(times)]
    behaviour = Counter(flag for t in history for flag in tx_flags(t))
    return Profile(
        address=address, address_type=address_type(address), stats=stats, info=info,
        txs_seen=len(history), history_complete=len(history) >= stats.tx_count,
        first_seen=times[0] if times else None, last_seen=times[-1] if times else None,
        longest_gap_days=round(max(gaps) / DAY, 1) if gaps else None,
        received_txs=len(received), sent_txs=len(signed), received_external=external,
        reused=stats.funded_txo_count > 1, behaviour=dict(sorted(behaviour.items())),
        fingerprint=summarize_fingerprints(signed),
    )
```

- [ ] **Step 5: Run the tests and lint.**
  - Run: `cd backend && uv run pytest tests/analysis/test_profile.py -v && uv run ruff check .`
  - Expected: 4 PASS, ruff clean.

- [ ] **Step 6: Commit.**

```bash
git add backend/btcintel/analysis backend/tests/analysis/test_profile.py
git commit -m "feat(analysis): analysis models and address profile (activity, behaviour, fingerprint)" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Exposure buckets

**Files:**
- Create: `backend/btcintel/analysis/exposure.py`
- Test: `backend/tests/analysis/test_exposure.py`

**Interfaces:**
- Consumes: `TraceResult` (`btcintel.trace.engine`) and `Stop.hops` from Task 1; `Bucket`, `Exposure`, `Direction` from Task 2; `Taxonomy.risk(id)`.
- Produces:
  - `compute_exposure(direction: Direction, result: TraceResult, total: float, *, taxonomy: Taxonomy, own_cluster: Callable[[str], bool]) -> Exposure`
  - `failed_exposure(direction: Direction, total: float, error: str) -> Exposure`
  - `REMAINDER_LABEL = "Fees or not reached (budget)"`
  - Bucket ordering: riskiest first, then by amount; the remainder is always last.

- [ ] **Step 1: Write the failing tests.** Create `backend/tests/analysis/test_exposure.py`:

```python
import pytest

from btcintel.analysis.exposure import compute_exposure, failed_exposure
from btcintel.catalog.loader import load_catalog
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from btcintel.trace.engine import TracePolicy, TraceResult, TraceSeed
from btcintel.trace.graph import GraphNode, Stop
from tests.builders import ADDR

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))
SEED, RW, EX, EX2 = ADDR[1], ADDR[9], ADDR[2], ADDR[10]


def addr_node(address, *, label, category, risk, stop_category, abuse=None, pack="p"):
    tag = {"address": address, "label": label, "category": category, "abuse": abuse, "pack": pack}
    return GraphNode(id=f"addr:{address}", kind="address", label=label, data={
        "address": address, "tags": [tag], "label": label, "category": category, "risk": risk,
        "stop_category": stop_category})


NODES = [
    addr_node(RW, label="LockBit", category="unknown", abuse="ransomware", risk="severe",
              stop_category="ransomware", pack="ransomwhere"),
    addr_node(EX, label="Binance", category="exchange", risk="low", stop_category="exchange"),
    addr_node(EX2, label="Binance", category="exchange", risk="low", stop_category="exchange"),
]


def result(stops, nodes=NODES, incomplete=False, reason=None):
    return TraceResult(seed=TraceSeed(address=SEED), policy=TracePolicy(), nodes=list(nodes), edges=[],
                       stops=stops, incomplete=incomplete, reason=reason, calls_used=7, txs_expanded=3)


def never(_address):
    return False


def test_buckets_group_stops_and_add_up_to_the_total():
    stops = [Stop(node=f"addr:{RW}", reason="labeled", taint=300_000, hops=2),
             Stop(node=f"addr:{EX}", reason="labeled", taint=400_000, hops=1),
             Stop(node=f"addr:{EX2}", reason="labeled", taint=100_000, hops=3),
             Stop(node=f"addr:{ADDR[8]}", reason="unspent", taint=150_000, hops=2),
             Stop(node=f"addr:{ADDR[11]}", reason="max_hops", taint=40_000, hops=4)]
    e = compute_exposure("backward", result(stops), 1_000_000, taxonomy=TAX, own_cluster=never)
    assert [(b.kind, b.label) for b in e.buckets] == [
        ("labeled", "LockBit"), ("labeled", "Binance"), ("unspent", "Still unspent"),
        ("limits", "Beyond the hop limit"), ("remainder", "Fees or not reached (budget)")]
    rw, ex = e.buckets[0], e.buckets[1]
    assert (rw.key, rw.risk, rw.source, rw.min_hops, rw.share) == ("ransomware", "severe", "ransomwhere", 2, 0.3)
    assert ex.amount == 500_000 and ex.min_hops == 1 and ex.nodes == [f"addr:{EX}", f"addr:{EX2}"]
    assert e.buckets[-1].amount == pytest.approx(10_000)
    assert sum(b.share for b in e.buckets) == pytest.approx(1.0)
    assert e.resolved_share == pytest.approx(0.95)  # limits and remainder are not endpoints
    assert (e.direction, e.total, e.calls_used) == ("backward", 1_000_000, 7)


def test_own_cluster_coinjoin_and_coinbase_buckets():
    stops = [Stop(node=f"addr:{EX}", reason="labeled", taint=200_000, hops=1),
             Stop(node="tx:" + "ab" * 32, reason="coinjoin", taint=300_000, detail="whirlpool", hops=2),
             Stop(node="tx:" + "cd" * 32, reason="coinbase", taint=500_000, hops=3)]
    e = compute_exposure("backward", result(stops), 1_000_000, taxonomy=TAX, own_cluster=lambda a: a == EX)
    by_kind = {b.kind: b for b in e.buckets}
    assert set(by_kind) == {"own_cluster", "coinjoin", "coinbase"}
    assert by_kind["own_cluster"].label == "Binance"
    assert by_kind["coinjoin"].label == "CoinJoin (whirlpool)" and by_kind["coinjoin"].risk == "medium"
    assert by_kind["coinbase"].label == "Newly mined coins"
    assert e.resolved_share == pytest.approx(1.0)


def test_zero_total_and_incomplete_trace():
    e = compute_exposure("forward", result([], incomplete=True, reason="API call budget of 120 exhausted"), 0,
                         taxonomy=TAX, own_cluster=never)
    assert e.buckets == [] and e.resolved_share == 0.0
    assert e.incomplete and "budget" in e.reason


def test_failed_exposure_is_all_remainder():
    e = failed_exposure("forward", 500_000, "NotFound: tx missing")
    assert [(b.kind, b.share) for b in e.buckets] == [("remainder", 1.0)]
    assert e.error == "NotFound: tx missing" and e.incomplete and e.resolved_share == 0.0
    assert failed_exposure("forward", 0, "boom").buckets == []
```

- [ ] **Step 2: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/analysis/test_exposure.py -v`
  - Expected: FAIL with `ModuleNotFoundError: No module named 'btcintel.analysis.exposure'`.

- [ ] **Step 3: Implement.** Create `backend/btcintel/analysis/exposure.py`:

```python
"""Where traced value ended: stops grouped into exposure buckets that add up to the traced total."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from btcintel.analysis.models import Bucket, Direction, Exposure
from btcintel.catalog.schema import RISK_ORDER
from btcintel.labels.taxonomy import Taxonomy
from btcintel.trace.engine import TraceResult
from btcintel.trace.graph import Stop

RESOLVED = frozenset({"labeled", "own_cluster", "coinjoin", "unspent", "coinbase"})
LIMIT_LABELS = {"max_hops": "Beyond the hop limit", "min_value": "Below the minimum value",
                "max_txs": "Beyond the transaction limit", "peel_off": "Peeled off"}
REMAINDER_LABEL = "Fees or not reached (budget)"
MAX_NODES = 5


def _bucket_for(stop: Stop, nodes: dict[str, dict[str, Any]], own_cluster: Callable[[str], bool],
                taxonomy: Taxonomy) -> Bucket:
    """An empty bucket describing where this stop's value ended."""
    if stop.reason == "labeled":
        data = nodes.get(stop.node, {})
        key = data.get("stop_category") or data.get("category") or "unknown"
        tag = next((t for t in data.get("tags", []) if key in (t.get("abuse"), t.get("category"))), {})
        own = own_cluster(stop.node.removeprefix("addr:"))
        return Bucket(kind="own_cluster" if own else "labeled", key=key,
                      label=tag.get("label") or data.get("label") or key,
                      risk=data.get("risk") or taxonomy.risk(key), source=tag.get("pack"))
    if stop.reason == "coinjoin":
        kind = stop.detail or "unknown"
        return Bucket(kind="coinjoin", key=kind, label=f"CoinJoin ({kind})", risk=taxonomy.risk("coinjoin"))
    if stop.reason == "unspent":
        return Bucket(kind="unspent", key="unspent", label="Still unspent")
    if stop.reason == "coinbase":
        return Bucket(kind="coinbase", key="coinbase", label="Newly mined coins")
    return Bucket(kind="limits", key=stop.reason, label=LIMIT_LABELS[stop.reason])


def compute_exposure(direction: Direction, result: TraceResult, total: float, *, taxonomy: Taxonomy,
                     own_cluster: Callable[[str], bool]) -> Exposure:
    nodes = {n.id: n.data for n in result.nodes}
    groups: dict[tuple[str, str, str], Bucket] = {}
    for stop in result.stops:
        b = _bucket_for(stop, nodes, own_cluster, taxonomy)
        k = (b.kind, b.key, b.label)
        g = groups.setdefault(k, b)
        hops = [h for h in (g.min_hops, stop.hops) if h is not None]
        keep = stop.node in g.nodes or len(g.nodes) >= MAX_NODES
        groups[k] = g.model_copy(update={"amount": g.amount + stop.taint, "min_hops": min(hops) if hops else None,
                                         "nodes": g.nodes if keep else [*g.nodes, stop.node]})
    buckets = list(groups.values())
    reached = sum(b.amount for b in buckets)
    if total - reached >= 1:
        buckets.append(Bucket(kind="remainder", key="remainder", label=REMAINDER_LABEL, amount=total - reached))
    base = max(total, reached)
    buckets = [b.model_copy(update={"share": b.amount / base if base else 0.0}) for b in buckets]
    buckets.sort(key=lambda b: (b.kind == "remainder", -RISK_ORDER[b.risk], -b.amount))
    resolved = sum(b.amount for b in buckets if b.kind in RESOLVED)
    return Exposure(direction=direction, total=total, buckets=buckets,
                    resolved_share=resolved / base if base else 0.0, incomplete=result.incomplete,
                    reason=result.reason, calls_used=result.calls_used)


def failed_exposure(direction: Direction, total: float, error: str) -> Exposure:
    """A trace that could not run: all of its value is 'not reached'."""
    buckets = [Bucket(kind="remainder", key="remainder", label=REMAINDER_LABEL, amount=total, share=1.0)] if total else []
    return Exposure(direction=direction, total=total, buckets=buckets, resolved_share=0.0, incomplete=True,
                    reason=error, error=error)
```

- [ ] **Step 4: Run the tests and lint.**
  - Run: `cd backend && uv run pytest tests/analysis/test_exposure.py -v && uv run ruff check .`
  - Expected: 4 PASS, ruff clean.

- [ ] **Step 5: Commit.**

```bash
git add backend/btcintel/analysis/exposure.py backend/tests/analysis/test_exposure.py
git commit -m "feat(analysis): exposure buckets from trace stops that add up to the traced total" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Explainable verdict

**Files:**
- Create: `backend/btcintel/analysis/verdict.py`
- Test: `backend/tests/analysis/test_verdict.py`

**Interfaces:**
- Consumes: `Bucket`, `ClusterSummary`, `Exposure`, `Reason`, `Verdict` (Task 2); `Taxonomy.risk`.
- Produces:
  - `build_verdict(address: str, info: dict[str, Any], cluster: ClusterSummary | None, exposures: list[Exposure], *, taxonomy: Taxonomy, hops: int, final: bool) -> Verdict`
  - `btc(sats: float) -> str`, e.g. `"0.015 BTC"`
  - `pct(share: float) -> str`, e.g. `"67%"` or `"4.0%"`
  - Rule ids: `own_label`, `cluster_label`, `direct_severe`, `high_share`, `high_minor`, `medium_share`, `medium_minor`, `low_only`, `nothing`.

Rule table (from the spec). `medium_minor` fills a gap the spec leaves open: medium exposure under 25% gives *low*, with a reason.

| Rule | Condition | Level |
|---|---|---|
| `own_label` | the address's own tag has risk ≥ medium | that risk |
| `cluster_label` | a cluster-inherited tag has risk ≥ medium | that risk, one lower if the cluster has conflicts |
| `direct_severe` | a labeled severe bucket with `min_hops == 1` | severe |
| `high_share` / `high_minor` | high+severe labeled share ≥ 10% / > 0 | high / medium |
| `medium_share` / `medium_minor` | medium labeled + CoinJoin share ≥ 25% / > 0 | medium / low |
| `low_only` | labeled buckets exist, none ≥ medium, no CoinJoin | low |
| `nothing` | no reason fired | none |

- [ ] **Step 1: Write the failing tests.** Create `backend/tests/analysis/test_verdict.py`:

```python
from btcintel.analysis.models import Bucket, ClusterSummary, Exposure, Reason
from btcintel.analysis.verdict import build_verdict
from btcintel.catalog.loader import load_catalog
from btcintel.cluster.expand import Conflict
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from tests.builders import ADDR

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))
A = ADDR[1]


def bucket(label, key, risk, share, *, hops=2, kind="labeled", source="p", total=1_000_000):
    return Bucket(kind=kind, key=key, label=label, risk=risk, source=source, amount=share * total, share=share,
                  min_hops=hops)


def exposure(direction, *buckets, total=1_000_000):
    resolved = sum(b.share for b in buckets if b.kind != "remainder")
    return Exposure(direction=direction, total=total, buckets=list(buckets), resolved_share=resolved)


def verdict(*exposures, info=None, cluster=None, final=True):
    return build_verdict(A, info or {"tags": []}, cluster, list(exposures), taxonomy=TAX, hops=3, final=final)


def tag(address, label, category, abuse=None, pack="p"):
    return {"address": address, "label": label, "category": category, "abuse": abuse, "pack": pack}


def test_own_severe_label_is_severe_even_before_tracing():
    v = verdict(info={"tags": [tag(A, "OFAC: Garantex", "organization", "sanctioned", "ofac_sdn")]}, final=False)
    assert v.level == "severe" and v.reasons[0].rule == "own_label"
    assert v.reasons[0].text == "Labeled OFAC: Garantex (sanctioned, ofac_sdn)"
    assert not v.final and v.coverage == "Tracing in progress…" and not v.low_confidence


def test_cluster_label_is_lowered_when_the_cluster_has_conflicts():
    info = {"tags": [tag(ADDR[5], "Helix", "mixing_service")]}
    clean = ClusterSummary(root=A, size=12, partial=False, capped=False)
    v = verdict(info=info, cluster=clean)
    assert v.level == "high" and v.reasons[0].text == "Its co-spend cluster (12 addresses) includes Helix (mixing_service, p)"
    messy = clean.model_copy(update={"conflicts": [Conflict(labels=["binance", "helix"], addresses=[A])]})
    v = verdict(info=info, cluster=messy)
    assert v.level == "medium" and "conflicting labels" in v.reasons[0].text


def test_direct_severe_exposure():
    v = verdict(exposure("backward", bucket("LockBit", "ransomware", "severe", 0.05, hops=1, source="ransomwhere")))
    assert v.level == "severe"
    assert v.reasons[0].text == "Received 0.0005 BTC directly from LockBit (ransomware, ransomwhere)"


def test_high_risk_share_thresholds():
    high = verdict(exposure("forward", bucket("Helix", "mixing_service", "high", 0.2)))
    assert high.level == "high" and high.reasons[0].rule == "high_share"
    assert high.reasons[0].text == "20% of outgoing funds (0.002 BTC) went to high-risk entities: Helix (within 2 hops)"
    minor = verdict(exposure("forward", bucket("Helix", "mixing_service", "high", 0.04)))
    assert minor.level == "medium" and minor.reasons[0].rule == "high_minor"


def test_medium_share_thresholds():
    cj = bucket("CoinJoin (whirlpool)", "whirlpool", "medium", 0.3, kind="coinjoin", source=None)
    assert verdict(exposure("forward", cj)).level == "medium"
    v = verdict(exposure("forward", cj.model_copy(update={"share": 0.1, "amount": 100_000})))
    assert v.level == "low" and v.reasons[0].rule == "medium_minor"


def test_only_low_risk_entities_is_low():
    v = verdict(exposure("backward", bucket("Binance", "exchange", "low", 0.6)))
    assert v.level == "low"
    assert v.reasons == [Reason(level="low", rule="low_only",
                                text="Incoming funds came from only low-risk known entities: Binance")]


def test_nothing_found_and_low_coverage():
    unspent = bucket("Still unspent", "unspent", "none", 0.3, kind="unspent", source=None)
    unresolved = bucket("Fees or not reached (budget)", "remainder", "none", 0.7, kind="remainder", source=None)
    v = verdict(exposure("forward", unspent, unresolved))
    assert v.level == "none" and v.reasons[0].text == "No known entity found within 3 hops"
    assert v.low_confidence
    assert v.coverage == "Traced 30% of funds to an endpoint within 3 hops; 70% not reached"


def test_reasons_are_sorted_worst_first():
    v = verdict(exposure("backward", bucket("Binance", "exchange", "low", 0.6)),
                exposure("forward", bucket("Helix", "mixing_service", "high", 0.2)))
    assert [r.level for r in v.reasons] == ["high", "low"] and v.level == "high"


def test_no_incoming_funds():
    v = verdict(exposure("backward", total=0), exposure("forward", total=0))
    assert v.level == "none" and not v.low_confidence and v.coverage.startswith("No incoming funds")
```

- [ ] **Step 2: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/analysis/test_verdict.py -v`
  - Expected: FAIL with `ModuleNotFoundError: No module named 'btcintel.analysis.verdict'`.

- [ ] **Step 3: Implement.** Create `backend/btcintel/analysis/verdict.py`:

```python
"""Explainable risk verdict: a level plus the plain-English reasons that produced it."""

from __future__ import annotations

from typing import Any

from btcintel.analysis.models import ClusterSummary, Exposure, Reason, Verdict
from btcintel.catalog.schema import RISK_ORDER
from btcintel.labels.taxonomy import Taxonomy

HIGH_SHARE = 0.10  # share of traced value involving high/severe entities that makes an address high risk
MEDIUM_SHARE = 0.25  # share involving medium entities (CoinJoin, gambling, swappers…) that makes it medium
LOW_COVERAGE = 0.5  # below this share of value traced to an endpoint the verdict is low confidence
LEVELS = ["none", "low", "medium", "high", "severe"]
MAX_LABEL_REASONS = 3
_WORDS = {"backward": ("Received", "from", "incoming", "came from"),
          "forward": ("Sent", "to", "outgoing", "went to")}


def btc(sats: float) -> str:
    return f"{sats / 100_000_000:.8f}".rstrip("0").rstrip(".") + " BTC"


def pct(share: float) -> str:
    return f"{share * 100:.1f}%" if share < 0.1 else f"{share * 100:.0f}%"


def _tag_risk(taxonomy: Taxonomy, tag: dict[str, Any]) -> str:
    return max(taxonomy.risk(tag.get("category")), taxonomy.risk(tag.get("abuse")), key=RISK_ORDER.__getitem__)


def _names(labels: list[str]) -> str:
    return ", ".join(list(dict.fromkeys(labels))[:3])


def label_reasons(address: str, info: dict[str, Any], cluster: ClusterSummary | None,
                  taxonomy: Taxonomy) -> list[Reason]:
    reasons: list[Reason] = []
    seen: set[str] = set()
    for tag in info.get("tags", []):
        level = _tag_risk(taxonomy, tag)
        if RISK_ORDER[level] < RISK_ORDER["medium"] or tag["label"] in seen:
            continue
        seen.add(tag["label"])
        what = f"{tag['label']} ({tag.get('abuse') or tag.get('category')}, {tag.get('pack') or tag.get('source')})"
        if tag.get("address") == address:
            reasons.append(Reason(level=level, rule="own_label", text=f"Labeled {what}"))
            continue
        where = f"Its co-spend cluster ({cluster.size} addresses)" if cluster else "Its co-spend cluster"
        text = f"{where} includes {what}"
        if cluster and cluster.conflicts:
            level = LEVELS[max(0, LEVELS.index(level) - 1)]
            text += "; the cluster has conflicting labels, so this may be a merge error"
        reasons.append(Reason(level=level, rule="cluster_label", text=text))
    return reasons[:MAX_LABEL_REASONS]


def exposure_reasons(e: Exposure) -> list[Reason]:
    if not e.total:
        return []
    verb, prep, noun, went = _WORDS[e.direction]
    labeled = [b for b in e.buckets if b.kind == "labeled"]
    reasons = [
        Reason(level="severe", rule="direct_severe",
               text=f"{verb} {btc(b.amount)} directly {prep} {b.label} ({b.key}{', ' + b.source if b.source else ''})")
        for b in labeled if b.risk == "severe" and b.min_hops == 1
    ]
    risky = [b for b in labeled if RISK_ORDER[b.risk] >= RISK_ORDER["high"]]
    if risky:
        share = sum(b.share for b in risky)
        hops = max(b.min_hops or 0 for b in risky)
        level, rule = ("high", "high_share") if share >= HIGH_SHARE else ("medium", "high_minor")
        reasons.append(Reason(level=level, rule=rule, text=(
            f"{pct(share)} of {noun} funds ({btc(sum(b.amount for b in risky))}) {went} high-risk entities: "
            f"{_names([b.label for b in risky])}{f' (within {hops} hops)' if hops else ''}")))
    medium = [b for b in e.buckets if b.kind in ("labeled", "coinjoin") and b.risk == "medium"]
    if medium:
        share = sum(b.share for b in medium)
        level, rule = ("medium", "medium_share") if share >= MEDIUM_SHARE else ("low", "medium_minor")
        reasons.append(Reason(level=level, rule=rule, text=(
            f"{pct(share)} of {noun} funds {went} medium-risk services: {_names([b.label for b in medium])}")))
    if labeled and not risky and not medium:
        reasons.append(Reason(level="low", rule="low_only", text=(
            f"{noun.capitalize()} funds {went} only low-risk known entities: {_names([b.label for b in labeled])}")))
    return reasons


def coverage_line(exposures: list[Exposure], hops: int) -> tuple[str, bool]:
    """Human coverage line and whether it is low enough to flag the verdict as low confidence."""
    if not exposures:
        return "Tracing in progress…", False
    total = sum(e.total for e in exposures)
    if not total:
        return "No incoming funds in the analysed history, so there was nothing to trace", False
    resolved = sum(e.resolved_share * e.total for e in exposures) / total
    return (f"Traced {pct(resolved)} of funds to an endpoint within {hops} hops; {pct(1 - resolved)} not reached",
            resolved < LOW_COVERAGE)


def build_verdict(address: str, info: dict[str, Any], cluster: ClusterSummary | None, exposures: list[Exposure],
                  *, taxonomy: Taxonomy, hops: int, final: bool) -> Verdict:
    reasons = label_reasons(address, info, cluster, taxonomy)
    for e in exposures:
        reasons += exposure_reasons(e)
    if not reasons:
        text = f"No known entity found within {hops} hops" if final else "No labels on this address; tracing its funds…"
        reasons = [Reason(level="none", rule="nothing", text=text)]
    reasons.sort(key=lambda r: -RISK_ORDER[r.level])
    coverage, low = coverage_line(exposures, hops) if final else ("Tracing in progress…", False)
    return Verdict(level=reasons[0].level, final=final, low_confidence=low, coverage=coverage, reasons=reasons)
```

- [ ] **Step 4: Run the tests and lint.**
  - Run: `cd backend && uv run pytest tests/analysis/test_verdict.py -v && uv run ruff check .`
  - Expected: 9 PASS, ruff clean.

- [ ] **Step 5: Commit.**

```bash
git add backend/btcintel/analysis/verdict.py backend/tests/analysis/test_verdict.py
git commit -m "feat(analysis): explainable risk verdict with coverage caveat" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Orchestration: `analyze_address`

**Files:**
- Create: `backend/btcintel/analysis/run.py`
- Create: `backend/tests/analysis_scenario.py`
- Test: `backend/tests/analysis/test_run.py`

**Interfaces:**
- Consumes:
  - Tasks 1–4.
  - `expand_cluster(seed, chain, uf, tags, policy) -> ExpandResult`, `ExpandPolicy`, `cluster_tags(root, uf, tags)` (`btcintel.cluster.expand`)
  - `trace(seed, policy, *, chain, labels, emit) -> TraceResult`
  - `LabelLookup(tags, taxonomy, uf, stop_categories)`
  - `UnionFind.root_of(address)` (read-only; unlike `find`, it never inserts)
- Produces:
  - `analyze_address(address: str, policy: AnalysisPolicy, *, chain: ChainSource, tags: TagStore, uf: UnionFind, taxonomy: Taxonomy, emit: Emit | None = None) -> AnalysisReport`
  - `analysis_stop_categories(taxonomy) -> list[str]`
- **Events, in order:**
  1. `section` "profile", then `section` "verdict" (`final: false`), then `progress` "profile"
  2. interleaved graph events (`nodes`/`edges`/`stop`) plus `section` "cluster" and `progress` per stage
  3. `section` "sources", "destinations", "profile" (labels re-read), then "verdict" (`final: true`)
  4. exactly one `{"type": "done", "incomplete", "reason", "calls_used"}`
- A section event looks like `{"type": "section", "name": str, "data": dict}`.
- Test helpers in `tests/analysis_scenario.py`: `A`, `R`, `build_funded()`, `ransomware_tag()`, `stores(tagged=True)`, `run_analysis(chain, *, address=A, tagged=True, policy=None)`.

- [ ] **Step 1: Create the test scenario.** Create `backend/tests/analysis_scenario.py`:

```python
"""Ransomware payer -> analysed address -> exchange / unspent: the graph the analysis tests run on."""

from dataclasses import dataclass

from btcintel.analysis.models import AnalysisPolicy
from btcintel.analysis.run import analyze_address
from btcintel.catalog.loader import load_catalog
from btcintel.chain.models import Tx
from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from tests.builders import ADDR, mk_tx
from tests.scenario import EX, U, scenario_tags

A, R = ADDR[1], ADDR[9]
TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))


@dataclass
class Funded:
    cb: Tx
    pay: Tx
    spend: Tx

    @property
    def txs(self) -> list[Tx]:
        return [self.cb, self.pay, self.spend]


def build_funded() -> Funded:
    """R (ransomware, mined coins) pays A 1.5M; A pays EX (exchange) 1M and U 499k (left unspent)."""
    cb = mk_tx([(None, 0)], [(R, 2_000_000)], coinbase=True)
    pay = mk_tx([(cb, 0)], [(A, 1_500_000), (R, 499_000)])
    spend = mk_tx([(pay, 0)], [(EX, 1_000_000), (U, 499_000)])
    return Funded(cb, pay, spend)


def ransomware_tag() -> Tag:
    # category "unknown" + abuse "ransomware": the shape of most imported ransomware tags
    return Tag(address=R, label="LockBit", category="unknown", abuse="ransomware", confidence="forensic",
               source="test", pack="ransomwhere")


def stores(tagged: bool = True) -> tuple[TagStore, UnionFind]:
    conn = open_intel_db(":memory:")
    tags = TagStore(conn)
    tags.add_many([*scenario_tags(), *([ransomware_tag()] if tagged else [])])
    return tags, UnionFind(conn)


async def run_analysis(chain, *, address=A, tagged=True, policy=None):
    tags, uf = stores(tagged)
    events: list[dict] = []
    report = await analyze_address(address, policy or AnalysisPolicy.quick(), chain=chain, tags=tags, uf=uf,
                                   taxonomy=TAX, emit=events.append)
    return report, events
```

- [ ] **Step 2: Write the failing tests.** Create `backend/tests/analysis/test_run.py`:

```python
import pytest

from tests.analysis_scenario import R, build_funded, run_analysis
from tests.fakes import FakeChain


async def test_analysis_finds_ransomware_source_and_exchange_destination():
    report, _ = await run_analysis(FakeChain(build_funded().txs))
    src = {b.label: b for b in report.sources.buckets}
    assert src["LockBit"].key == "ransomware" and src["LockBit"].min_hops == 1
    assert src["LockBit"].share == pytest.approx(1.0)
    dst = {b.label: b for b in report.destinations.buckets}
    assert dst["Example Exchange"].share == pytest.approx(1_000_000 / 1_500_000, rel=1e-3)
    assert dst["Still unspent"].min_hops == 1
    assert report.verdict.level == "severe" and report.verdict.final
    assert [r.rule for r in report.verdict.reasons] == ["direct_severe", "high_share", "low_only"]
    assert report.profile.received_external == 1_500_000 and report.cluster.size == 1
    assert report.depth == "quick" and report.calls_used > 0


async def test_analysis_streams_sections_graph_and_one_done():
    report, events = await run_analysis(FakeChain(build_funded().txs))
    sections = [e["name"] for e in events if e["type"] == "section"]
    assert sections[:2] == ["profile", "verdict"] and sections[-1] == "verdict"
    assert {"cluster", "sources", "destinations"} <= set(sections)
    first_verdict = next(e for e in events if e["type"] == "section" and e["name"] == "verdict")
    assert first_verdict["data"]["final"] is False
    assert any(e["type"] == "nodes" for e in events) and any(e["type"] == "stop" for e in events)
    assert [e["type"] for e in events].count("done") == 1 and events[-1]["type"] == "done"
    assert events[-1]["calls_used"] == report.calls_used and not events[-1]["incomplete"]


async def test_a_labeled_address_still_shows_where_its_funds_went():
    report, _ = await run_analysis(FakeChain(build_funded().txs), address=R)
    assert report.verdict.level == "severe" and report.verdict.reasons[0].rule == "own_label"
    assert "Example Exchange" in {b.label for b in report.destinations.buckets}
    assert {b.kind for b in report.sources.buckets} == {"coinbase"}


async def test_unused_address_gives_an_empty_but_complete_report():
    report, _ = await run_analysis(FakeChain([]))
    assert report.profile.txs_seen == 0
    assert report.sources.buckets == [] and report.destinations.buckets == []
    assert report.verdict.level == "none" and report.verdict.coverage.startswith("No incoming funds")


async def test_a_failing_trace_direction_is_reported_not_fatal():
    sc = build_funded()
    # R untagged and its funding coinbase missing: the backward trace hits NotFound for sc.cb
    report, events = await run_analysis(FakeChain([sc.pay, sc.spend]), tagged=False)
    assert report.sources.error.startswith("NotFound") and report.sources.buckets[0].kind == "remainder"
    assert "Example Exchange" in {b.label for b in report.destinations.buckets}
    assert events[-1]["type"] == "done" and events[-1]["incomplete"]
```

- [ ] **Step 3: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/analysis/test_run.py -v`
  - Expected: FAIL with `ModuleNotFoundError: No module named 'btcintel.analysis.run'` (raised while importing `tests.analysis_scenario`).

- [ ] **Step 4: Implement.** Create `backend/btcintel/analysis/run.py`:

```python
"""Automatic address analysis as one job: profile, cluster, sources and destinations, verdict."""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from contextlib import aclosing
from typing import Any

from btcintel.analysis.exposure import compute_exposure, failed_exposure
from btcintel.analysis.models import AnalysisPolicy, AnalysisReport, ClusterSummary, Direction, Exposure
from btcintel.analysis.profile import build_profile
from btcintel.analysis.verdict import build_verdict
from btcintel.chain.budget import CallBudget, budget_scope
from btcintel.chain.errors import ChainError
from btcintel.chain.source import ChainSource
from btcintel.chain.validate import normalize_address
from btcintel.cluster.expand import ExpandPolicy, ExpandResult, cluster_tags, expand_cluster
from btcintel.cluster.unionfind import UnionFind
from btcintel.labels.lookup import LabelLookup
from btcintel.labels.store import TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.trace.engine import TracePolicy, TraceResult, TraceSeed, trace
from btcintel.trace.graph import Emit

TOP_CLUSTER_LABELS = 5


def _ignore(event: dict[str, Any]) -> None:
    return None


def analysis_stop_categories(taxonomy: Taxonomy) -> list[str]:
    """Analysis traces stop at every labeled entity, abuse labels included, so each traced satoshi
    ends at exactly one endpoint and the exposure shares add up."""
    return sorted(set(taxonomy.categories) - {"unknown"})


def summarize_cluster(result: ExpandResult, uf: UnionFind, tags: TagStore) -> ClusterSummary:
    counts = Counter((t.label, t.category, t.abuse) for t in cluster_tags(result.root, uf, tags))
    top = [{"label": label, "category": category, "abuse": abuse, "count": n}
           for (label, category, abuse), n in counts.most_common(TOP_CLUSTER_LABELS)]
    return ClusterSummary(root=result.root, size=result.size, partial=result.partial, capped=result.capped,
                          conflicts=result.conflicts, top_labels=top, calls_used=result.calls_used)


async def analyze_address(address: str, policy: AnalysisPolicy, *, chain: ChainSource, tags: TagStore,
                          uf: UnionFind, taxonomy: Taxonomy, emit: Emit | None = None) -> AnalysisReport:
    address = normalize_address(address)
    send = emit or _ignore
    calls = 0

    def section(name: str, data: Any) -> None:
        send({"type": "section", "name": name, "data": data.model_dump()})

    def progress(stage: str) -> None:
        send({"type": "progress", "stage": stage, "calls": calls})

    # 1. Profile: a few calls. The fetched tx bodies are cached, so the traces reuse them.
    budget = CallBudget(policy.history_txs // 25 + 10)
    with budget_scope(budget):
        stats = await chain.get_address(address)
        async with aclosing(chain.iter_address_txs(address, policy.history_txs)) as txs:
            history = [tx async for tx in txs]
    calls = budget.used
    profile = build_profile(address, stats, history, LabelLookup(tags, taxonomy, uf).lookup(address).to_dict())
    section("profile", profile)
    section("verdict", build_verdict(address, profile.info, None, [], taxonomy=taxonomy,
                                     hops=policy.trace_hops, final=False))
    progress("profile")

    # 2. Cluster, sources and destinations run concurrently, each inside its own call budget.
    stop_categories = analysis_stop_categories(taxonomy)
    trace_labels = LabelLookup(tags, taxonomy, uf, stop_categories)

    def graph_event(event: dict[str, Any]) -> None:
        if event["type"] != "done":  # the analysis sends one "done" of its own at the end
            send(event)

    async def run_cluster() -> ClusterSummary:
        nonlocal calls
        try:
            result = await expand_cluster(address, chain, uf, tags, ExpandPolicy(
                max_addresses=policy.cluster_addresses, max_calls=policy.cluster_calls,
                max_txs_per_address=policy.history_txs))
            summary = summarize_cluster(result, uf, tags)
        except ChainError as e:
            summary = ClusterSummary(root=address, size=1, partial=True, capped=False,
                                     error=f"{type(e).__name__}: {e}")
        calls += summary.calls_used
        section("cluster", summary)
        progress("cluster")
        return summary

    async def run_trace(direction: Direction) -> TraceResult | str:
        nonlocal calls
        tp = TracePolicy(direction=direction, max_hops=policy.trace_hops, max_txs=policy.trace_txs,
                         max_calls=policy.trace_calls, min_value_sats=policy.min_value_sats,
                         taint_model="haircut", stop_categories=stop_categories,
                         max_address_txs=policy.history_txs)
        try:
            result = await trace(TraceSeed(address=address), tp, chain=chain, labels=trace_labels,
                                 emit=graph_event)
        except ChainError as e:  # e.g. NotFound mid-trace; the other stages still complete
            progress(direction)
            return f"{type(e).__name__}: {e}"
        calls += result.calls_used
        progress(direction)
        return result

    cluster, back, fwd = await asyncio.gather(run_cluster(), run_trace("backward"), run_trace("forward"))

    # 3. Exposure per direction. Value ending inside the address's own cluster is not exposure.
    root = uf.root_of(address)

    def own_cluster(other: str) -> bool:
        return root is not None and uf.root_of(other) == root

    def exposure(direction: Direction, result: TraceResult | str) -> Exposure:
        if isinstance(result, str):
            return failed_exposure(direction, profile.received_external, result)
        return compute_exposure(direction, result, profile.received_external, taxonomy=taxonomy,
                                own_cluster=own_cluster)

    sources, destinations = exposure("backward", back), exposure("forward", fwd)
    section("sources", sources)
    section("destinations", destinations)

    # 4. Final verdict, with labels re-read now that the cluster may have grown.
    profile = profile.model_copy(update={"info": LabelLookup(tags, taxonomy, uf).lookup(address).to_dict()})
    section("profile", profile)
    verdict = build_verdict(address, profile.info, cluster, [sources, destinations], taxonomy=taxonomy,
                            hops=policy.trace_hops, final=True)
    section("verdict", verdict)
    report = AnalysisReport(address=address, depth=policy.depth, generated_at=time.time(), profile=profile,
                            cluster=cluster, sources=sources, destinations=destinations, verdict=verdict,
                            calls_used=calls)
    stopped = [e.reason for e in (sources, destinations) if e.incomplete and e.reason]
    send({"type": "done", "incomplete": bool(stopped), "reason": "; ".join(stopped) or None, "calls_used": calls})
    return report
```

- [ ] **Step 5: Run the tests and lint.**
  - Run: `cd backend && uv run pytest tests/analysis -v && uv run ruff check .`
  - Expected: all analysis tests PASS, ruff clean.

- [ ] **Step 6: Commit.**

```bash
git add backend/btcintel/analysis/run.py backend/tests/analysis_scenario.py backend/tests/analysis/test_run.py
git commit -m "feat(analysis): analyze_address orchestrates profile, cluster, traces and verdict" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Markdown report

**Files:**
- Create: `backend/btcintel/analysis/report.py`
- Modify: `backend/btcintel/analysis/run.py` (attach the markdown before the `done` event)
- Test: `backend/tests/analysis/test_report.py`

**Interfaces:**
- Consumes: `AnalysisReport` (Task 2); `btc`, `pct` (Task 4); `run_analysis` (Task 5 helper).
- Produces: `to_markdown(report: AnalysisReport) -> str`. `analyze_address` now returns a report whose `markdown` field is filled in.

- [ ] **Step 1: Write the failing tests.** Create `backend/tests/analysis/test_report.py`:

```python
from btcintel.analysis.report import to_markdown
from tests.analysis_scenario import A, build_funded, run_analysis
from tests.fakes import FakeChain


async def test_markdown_report_has_verdict_reasons_and_tables():
    report, _ = await run_analysis(FakeChain(build_funded().txs))
    md = report.markdown
    assert md == to_markdown(report)
    assert md.startswith(f"# Address analysis: {A}\n")
    assert "**Verdict: SEVERE**" in md
    assert "- **severe**: Received 0.015 BTC directly from LockBit (ransomware, ransomwhere)" in md
    assert "## Sources of funds" in md and "| LockBit | ransomware | 0.015 BTC | 100% | 1 | ransomwhere |" in md
    assert "## Destinations of funds" in md and "| Example Exchange | exchange | 0.01 BTC | 67% | 1 | test |" in md
    assert "| Wallet fingerprint | v2|" not in md  # pipes in values are escaped
    assert "v2\\|lt:zero" in md


async def test_markdown_for_an_unused_address():
    report, _ = await run_analysis(FakeChain([]))
    assert report.markdown.count("No funds to trace.") == 2
    assert "**Verdict: NONE**" in report.markdown
```

- [ ] **Step 2: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/analysis/test_report.py -v`
  - Expected: FAIL with `ModuleNotFoundError: No module named 'btcintel.analysis.report'`.

- [ ] **Step 3: Implement.** Create `backend/btcintel/analysis/report.py`:

```python
"""Markdown rendering of an analysis report (CLI output and case notes)."""

from __future__ import annotations

from datetime import UTC, datetime

from btcintel.analysis.models import AnalysisReport, Exposure
from btcintel.analysis.verdict import btc, pct


def _date(ts: float | None) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d") if ts else "—"


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|")


def _exposure_lines(title: str, e: Exposure | None) -> list[str]:
    lines = [f"## {title}", ""]
    if e is not None and e.error:
        lines += [f"Trace failed: {e.error}", ""]
    if e is None or not e.buckets:
        return [*lines, "No funds to trace.", ""]
    lines += ["| Where | Category | Amount | Share | Hops | Source |", "|---|---|---|---|---|---|"]
    for b in e.buckets:
        if b.kind == "labeled":
            category = b.key
        elif b.kind == "own_cluster":
            category = f"{b.key} (own cluster)"
        else:
            category = b.kind.replace("_", " ")
        hops = "—" if b.min_hops is None else str(b.min_hops)
        lines.append(f"| {_cell(b.label)} | {category} | {btc(b.amount)} | {pct(b.share)} | {hops} | "
                     f"{_cell(b.source or '—')} |")
    if e.incomplete and e.reason and not e.error:
        lines += ["", f"Stopped early: {e.reason}"]
    return [*lines, ""]


def to_markdown(r: AnalysisReport) -> str:
    p, v, c = r.profile, r.verdict, r.cluster
    labels = ", ".join(f"{t['label']} ({t.get('abuse') or t['category']})" for t in p.info.get("tags", [])[:5])
    behaviour = ", ".join(f"{k} ×{n}" for k, n in p.behaviour.items())
    fp = p.fingerprint
    fingerprint = (f"{fp.signature} in {pct(fp.share)} of {fp.signed_txs} signed txs" if fp.signed_txs
                   else "no signed transactions")
    quiet = "—" if p.longest_gap_days is None else f"{p.longest_gap_days:g} days"
    lines = [
        f"# Address analysis: {r.address}", "",
        f"**Verdict: {v.level.upper()}**{' (low confidence: try a deeper analysis)' if v.low_confidence else ''}  ",
        f"{r.depth.capitalize()} analysis · {_date(r.generated_at)} · {r.calls_used} API calls  ",
        v.coverage, "",
        "## Why", "",
        *[f"- **{x.level}**: {x.text}" for x in v.reasons], "",
        "## Profile", "",
        "| | |", "|---|---|",
        f"| Address type | {p.address_type or 'unknown'}{' (reused)' if p.reused else ''} |",
        f"| Balance | {btc(p.stats.balance)} |",
        f"| Received / sent | {btc(p.stats.funded_sum)} / {btc(p.stats.spent_sum)} |",
        f"| Transactions | {p.stats.tx_count} ({p.txs_seen} analysed) |",
        f"| Active | {_date(p.first_seen)}{'' if p.history_complete else ' or earlier'} → {_date(p.last_seen)} |",
        f"| Longest quiet period | {quiet} |",
        f"| Labels | {_cell(labels or 'none')} |",
        f"| Behaviour | {_cell(behaviour or 'nothing notable')} |",
        f"| Wallet fingerprint | {_cell(fingerprint)} |", "",
        "## Cluster", "",
    ]
    if c is None:
        lines += ["Not expanded.", ""]
    else:
        lines.append(f"- Size: {c.size} addresses{' (partial)' if c.partial else ''}"
                     f"{'; capped, likely a large service' if c.capped else ''}")
        if c.top_labels:
            lines.append("- Labels: " + ", ".join(f"{t['label']} ×{t['count']}" for t in c.top_labels))
        if c.conflicts:
            lines.append("- Conflicting labels: " + "; ".join(" / ".join(x.labels) for x in c.conflicts))
        if c.error:
            lines.append(f"- Expansion failed: {c.error}")
        lines.append("")
    lines += _exposure_lines("Sources of funds", r.sources)
    lines += _exposure_lines("Destinations of funds", r.destinations)
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Attach the markdown in `run.py`.** Add `from btcintel.analysis.report import to_markdown` to the imports. Then replace the `report = AnalysisReport(...)` statement with:

```python
    report = AnalysisReport(address=address, depth=policy.depth, generated_at=time.time(), profile=profile,
                            cluster=cluster, sources=sources, destinations=destinations, verdict=verdict,
                            calls_used=calls)
    report = report.model_copy(update={"markdown": to_markdown(report)})
```

- [ ] **Step 5: Run the tests and lint.**
  - Run: `cd backend && uv run pytest tests/analysis -v && uv run ruff check .`
  - Expected: all PASS, ruff clean.

- [ ] **Step 6: Commit.**

```bash
git add backend/btcintel/analysis/report.py backend/btcintel/analysis/run.py backend/tests/analysis/test_report.py
git commit -m "feat(analysis): Markdown rendering of the analysis report" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `POST /api/analyze` and `btcintel analyze`

**Files:**
- Create: `backend/btcintel/api/routes_analysis.py`
- Modify: `backend/btcintel/api/app.py` (import list and router tuple)
- Modify: `backend/btcintel/cli.py` (the command and its parser)
- Test: `backend/tests/api/test_analysis_api.py`, `backend/tests/test_cli_analyze.py`

**Interfaces:**
- Consumes: `analyze_address`, `AnalysisPolicy.quick()` / `.deep()`; `JobManager.start(kind, fn)`; `valid_address()` (`btcintel.api.deps`), which returns 400 for invalid input and normalizes case.
- Produces:
  - `POST /api/analyze` with body `{"address": str, "depth": "quick" | "deep"}`. It returns 202 `{"job_id"}`; the job kind is `"analysis"` and its result is `AnalysisReport.model_dump()`.
  - CLI `btcintel analyze <address> [--deep] [--json]`.

- [ ] **Step 1: Write the failing API tests.** Create `backend/tests/api/test_analysis_api.py`:

```python
import json

from tests.analysis_scenario import A, build_funded, ransomware_tag
from tests.api.conftest import wait_job
from tests.fakes import FakeChain


def test_analyze_job_streams_sections_and_returns_the_report(make_client):
    client = make_client(FakeChain(build_funded().txs))
    client.app.state.rt.tags.add_many([ransomware_tag()])
    r = client.post("/api/analyze", json={"address": A.upper()})
    assert r.status_code == 202
    job = wait_job(client, r.json()["job_id"])
    assert job["status"] == "done" and job["kind"] == "analysis"
    result = job["result"]
    assert result["address"] == A and result["depth"] == "quick"
    assert result["verdict"]["level"] == "severe" and result["markdown"].startswith(f"# Address analysis: {A}")
    with client.stream("GET", f"/api/jobs/{job['id']}/events") as stream:
        events = [json.loads(line[6:]) for line in stream.iter_lines() if line.startswith("data: ")]
    names = [e["name"] for e in events if e["type"] == "section"]
    assert names[0] == "profile" and names[-1] == "verdict"
    assert events[-2]["type"] == "done"
    assert events[-1] == {"seq": len(events) - 1, "type": "status", "status": "done", "error": None}


def test_analyze_rejects_bad_input(client):
    assert client.post("/api/analyze", json={"address": "nope"}).status_code == 400
    assert client.post("/api/analyze", json={"address": A, "depth": "huge"}).status_code == 422
```

- [ ] **Step 2: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/api/test_analysis_api.py -v`
  - Expected: FAIL with 404 (`assert 404 == 202`), because the route doesn't exist yet.

- [ ] **Step 3: Implement the route.** Create `backend/btcintel/api/routes_analysis.py`:

```python
"""Automatic address analysis jobs."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from btcintel.analysis.models import AnalysisPolicy
from btcintel.analysis.run import analyze_address
from btcintel.api.deps import rt, valid_address
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


class AnalyzeRequest(BaseModel):
    address: str
    depth: Literal["quick", "deep"] = "quick"


@router.post("/analyze", status_code=202)
async def start_analysis(req: AnalyzeRequest, s: AppState = Depends(rt)) -> dict[str, str]:
    address = valid_address(req.address)
    policy = AnalysisPolicy.deep() if req.depth == "deep" else AnalysisPolicy.quick()

    async def run(emit):
        report = await analyze_address(address, policy, chain=s.chain, tags=s.tags, uf=s.uf,
                                       taxonomy=s.taxonomy, emit=emit)
        return report.model_dump()

    return {"job_id": s.jobs.start("analysis", run).id}
```

- [ ] **Step 4: Register the router.** In `backend/btcintel/api/app.py`, add `routes_analysis,` to the `from btcintel.api import (...)` list (keep it alphabetical, first) and change the router loop to:

```python
    for module in (routes_chain, routes_trace, routes_analysis, routes_cluster, routes_tags, routes_cases, routes_kb):
        app.include_router(module.router)
```

- [ ] **Step 5: Run the API tests.**
  - Run: `cd backend && uv run pytest tests/api -v`
  - Expected: all PASS.

- [ ] **Step 6: Write the failing CLI tests.** Create `backend/tests/test_cli_analyze.py`:

```python
import json
from contextlib import asynccontextmanager

import btcintel.runtime as runtime
from btcintel.cli import main
from tests.analysis_scenario import A, build_funded, ransomware_tag
from tests.fakes import FakeChain
from tests.scenario import scenario_tags


def use_fake_chain(monkeypatch, tmp_path):
    real = runtime.open_runtime

    @asynccontextmanager
    async def with_fake_chain(settings, chain=None):
        async with real(settings, FakeChain(build_funded().txs)) as rt:
            rt.tags.add_many([*scenario_tags(), ransomware_tag()])
            yield rt

    monkeypatch.setenv("BTCINTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(runtime, "open_runtime", with_fake_chain)


def test_analyze_prints_the_markdown_report(tmp_path, monkeypatch, capsys):
    use_fake_chain(monkeypatch, tmp_path)
    assert main(["analyze", A]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"# Address analysis: {A}\n") and "**Verdict: SEVERE**" in out


def test_analyze_json_and_bad_address(tmp_path, monkeypatch, capsys):
    use_fake_chain(monkeypatch, tmp_path)
    assert main(["analyze", A, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"]["level"] == "severe"
    assert main(["analyze", "nope"]) == 2
```

- [ ] **Step 7: Run it and check it fails.**
  - Run: `cd backend && uv run pytest tests/test_cli_analyze.py -v`
  - Expected: FAIL. argparse exits with `SystemExit: 2` (`invalid choice: 'analyze'`).

- [ ] **Step 8: Implement the CLI command.** In `backend/btcintel/cli.py`, add after `_cluster` (before the `COMMANDS.update(...)` line):

```python
def _cmd_analyze(args: argparse.Namespace) -> int:
    if not is_address(args.address):
        print("invalid address", file=sys.stderr)
        return 2
    return asyncio.run(_analyze(args))


async def _analyze(args: argparse.Namespace) -> int:
    from btcintel.analysis.models import AnalysisPolicy
    from btcintel.analysis.run import analyze_address
    from btcintel.runtime import open_runtime

    policy = AnalysisPolicy.deep() if args.deep else AnalysisPolicy.quick()
    async with open_runtime(load_settings()) as rt:
        try:
            report = await analyze_address(args.address, policy, chain=rt.chain, tags=rt.tags, uf=rt.uf,
                                           taxonomy=rt.taxonomy)
        except ChainError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    sys.stdout.write(report.model_dump_json(indent=2) + "\n" if args.json else report.markdown)
    return 0
```

Change the registration line to:

```python
COMMANDS.update({"serve": _cmd_serve, "tx": _cmd_tx, "trace": _cmd_trace, "cluster": _cmd_cluster,
                 "analyze": _cmd_analyze})
```

In `_build_parser`, add after the `cluster` subparser lines:

```python
    an = sub.add_parser("analyze", help="automatic analysis of an address: risk, sources, destinations, profile")
    an.add_argument("address")
    an.add_argument("--deep", action="store_true", help="larger budgets (5-10 min on public APIs)")
    an.add_argument("--json", action="store_true", help="print the full report as JSON")
```

- [ ] **Step 9: Run the full suite and lint.**
  - Run: `cd backend && uv run pytest -q && uv run ruff check .`
  - Expected: all PASS, ruff clean.

- [ ] **Step 10: Commit.**

```bash
git add backend/btcintel/api/routes_analysis.py backend/btcintel/api/app.py backend/btcintel/cli.py \
  backend/tests/api/test_analysis_api.py backend/tests/test_cli_analyze.py
git commit -m "feat(api): POST /api/analyze job and btcintel analyze command" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Web: types, client, route and store actions

**Files:**
- Modify: `web/src/api/types.ts`, `web/src/api/client.ts`
- Modify: `web/src/lib/route.ts`, `web/src/lib/route.test.ts`
- Modify: `web/src/state/store.ts`, `web/src/state/actions.ts`, `web/src/state/actions.test.ts`

**Interfaces:**
- Consumes: the backend events and report from Tasks 5–7.
- Produces:
  - TypeScript types matching the backend models: `Depth`, `Profile`, `FingerprintSummary`, `ClusterSummary`, `Bucket`, `BucketKind`, `Exposure`, `Reason`, `Verdict`, `AnalysisReport`, `AnalysisSections`, `SectionEvent`; `Stop.hops?: number | null`.
  - `api.analyze(address: string, depth?: Depth) -> Promise<{ job_id: string }>`
  - Route `{ view: "analysis"; address: string }`, with hash `#/analysis/<encoded address>`.
  - Store: `analysis: AnalysisState | null`, where `AnalysisState = { address, depth, sections: AnalysisSections, markdown: string | null }`; `setAnalysis`, `patchAnalysis`, `patchSections`; `JobState.kind` includes `"analysis"`.
  - Actions:
    - `startAnalysis(address: string, depth?: Depth): Promise<boolean>`, which is false when the user kept their unsaved work
    - `saveAnalysisAsCase()`
    - `hasUnsavedWork(): boolean`
    - `search()` navigates address results to `#/analysis/<address>`

- [ ] **Step 1: Write the failing route test.** In `web/src/lib/route.test.ts`, add:

```ts
test("parses the analysis route", () => {
  expect(parseHash("#/analysis/bc1qxyz")).toEqual({ view: "analysis", address: "bc1qxyz" });
  expect(parseHash("#/analysis/")).toEqual({ view: "graph" });
  expect(routeToHash({ view: "analysis", address: "bc1qxyz" })).toBe("#/analysis/bc1qxyz");
});
```

- [ ] **Step 2: Write the failing action tests.** In `web/src/state/actions.test.ts`, add `analyze: vi.fn(), job: vi.fn(),` to the mocked `api` object, then append:

```ts
test("search for an address opens its analysis page", async () => {
  mocked.search.mockResolvedValue({ kind: "address", query: "bc1qaddr" });
  await actions.search("bc1qaddr");
  expect(window.location.hash).toBe("#/analysis/bc1qaddr");
});

test("startAnalysis streams sections and graph events, then fetches the markdown", async () => {
  mocked.analyze.mockResolvedValue({ job_id: "a1" });
  mocked.job.mockResolvedValue({ id: "a1", kind: "analysis", status: "done", error: null, events: 5, result: { markdown: "# Address analysis" } });
  expect(await actions.startAnalysis("bc1qaddr")).toBe(true);
  expect(mocked.analyze).toHaveBeenCalledWith("bc1qaddr", "quick");
  const emit = handlers.onEvent!;
  emit({ seq: 0, type: "section", name: "verdict", data: { level: "severe", final: false, low_confidence: false, coverage: "Tracing in progress…", reasons: [] } });
  emit({ seq: 1, type: "nodes", items: [{ id: "addr:bc1qaddr", kind: "address", label: "bc1qaddr", data: {} }] });
  emit({ seq: 2, type: "progress", stage: "cluster", calls: 12 });
  emit({ seq: 3, type: "done", incomplete: false, reason: null, calls_used: 40 });
  emit({ seq: 4, type: "status", status: "done", error: null });
  await vi.waitFor(() => expect(useWorkbench.getState().analysis?.markdown).toBe("# Address analysis"));
  const s = useWorkbench.getState();
  expect(s.analysis?.sections.verdict?.level).toBe("severe");
  expect(s.graph.nodes["addr:bc1qaddr"]).toBeDefined();
  expect(s.job).toMatchObject({ kind: "analysis", status: "done", calls: 40, nodes: 1 });
});

test("a new analysis asks before discarding a hand-built graph, but not a previous analysis", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  mocked.tx.mockResolvedValue(txResponse);
  mocked.cancelJob.mockResolvedValue({ cancelled: true });
  await actions.openTx(TXID); // hand-built: dirty, no case, no analysis
  expect(await actions.startAnalysis("bc1qaddr")).toBe(false);
  expect(mocked.analyze).not.toHaveBeenCalled();
  expect(useWorkbench.getState().graph.nodes[`tx:${TXID}`]).toBeDefined();
  confirm.mockReturnValue(true);
  mocked.analyze.mockResolvedValue({ job_id: "a2" });
  expect(await actions.startAnalysis("bc1qaddr")).toBe(true);
  expect(confirm).toHaveBeenCalledTimes(2);
  const first = handlers.onEvent!;
  first({ seq: 0, type: "nodes", items: [{ id: "addr:x", kind: "address", label: "x", data: {} }] });
  expect(useWorkbench.getState().dirty).toBe(true);
  expect(await actions.startAnalysis("bc1qother", "deep")).toBe(true); // an analysis graph: no prompt
  expect(confirm).toHaveBeenCalledTimes(2);
  expect(mocked.cancelJob).toHaveBeenCalledWith("a2");
  first({ seq: 1, type: "nodes", items: [{ id: "addr:leak", kind: "address", label: "leak", data: {} }] });
  const s = useWorkbench.getState();
  expect(s.graph.nodes["addr:leak"]).toBeUndefined();
  expect(s.analysis).toMatchObject({ address: "bc1qother", depth: "deep" });
  confirm.mockRestore();
});

test("saving an analysis names the case and puts the report into empty notes", async () => {
  mocked.analyze.mockResolvedValue({ job_id: "a3" });
  await actions.startAnalysis("bc1qverylongaddress0000");
  useWorkbench.getState().patchAnalysis({ markdown: "# Report" });
  mocked.createCase.mockResolvedValue({ id: "c1", name: "Analysis of bc1qvery…0000", notes: "# Report", graph: {}, created_at: 1, updated_at: 1, watch: [] });
  await actions.saveAnalysisAsCase();
  expect(mocked.createCase).toHaveBeenCalledWith(expect.objectContaining({ name: "Analysis of bc1qvery…0000", notes: "# Report" }));
});
```

- [ ] **Step 3: Run them and check they fail.**
  - Run: `cd web && npx vitest run src/lib/route.test.ts src/state/actions.test.ts`
  - Expected: the new tests FAIL (the analysis route parses as `graph`, and `actions.startAnalysis is not a function`).

- [ ] **Step 4: Add the types.** In `web/src/api/types.ts`:
  - Change `Stop` to `export interface Stop { node: string; reason: StopReason; taint: number; detail: string; hops?: number | null }`.
  - Add `stage?: string` to the `progress` event.
  - Add `| ({ type: "section" } & SectionEvent)` to the `JobEvent` union.
  - Append:

```ts
export type Depth = "quick" | "deep";
export interface FingerprintSummary { signed_txs: number; signature: string | null; share: number; traits: Record<string, unknown> }
export interface Profile {
  address: string; address_type: string | null; stats: AddressStats; info: AddressInfo;
  txs_seen: number; history_complete: boolean; first_seen: number | null; last_seen: number | null;
  longest_gap_days: number | null; received_txs: number; sent_txs: number; received_external: number;
  reused: boolean; behaviour: Record<string, number>; fingerprint: FingerprintSummary;
}
export interface ClusterSummary {
  root: string; size: number; partial: boolean; capped: boolean;
  conflicts: { labels: string[]; addresses: string[] }[];
  top_labels: { label: string; category: string; abuse: string | null; count: number }[];
  calls_used: number; error: string | null;
}
export type BucketKind = "labeled" | "own_cluster" | "coinjoin" | "unspent" | "coinbase" | "limits" | "remainder";
export interface Bucket {
  kind: BucketKind; key: string; label: string; risk: RiskLevel; source: string | null;
  amount: number; share: number; min_hops: number | null; nodes: string[];
}
export interface Exposure {
  direction: "backward" | "forward"; total: number; buckets: Bucket[]; resolved_share: number;
  incomplete: boolean; reason: string | null; calls_used: number; error: string | null;
}
export interface Reason { level: RiskLevel; rule: string; text: string }
export interface Verdict { level: RiskLevel; final: boolean; low_confidence: boolean; coverage: string; reasons: Reason[] }
export interface AnalysisSections {
  profile?: Profile; cluster?: ClusterSummary; sources?: Exposure; destinations?: Exposure; verdict?: Verdict;
}
export type SectionEvent =
  | { name: "profile"; data: Profile }
  | { name: "cluster"; data: ClusterSummary }
  | { name: "sources"; data: Exposure }
  | { name: "destinations"; data: Exposure }
  | { name: "verdict"; data: Verdict };
export interface AnalysisReport {
  address: string; depth: Depth; generated_at: number; profile: Profile; cluster: ClusterSummary | null;
  sources: Exposure | null; destinations: Exposure | null; verdict: Verdict; calls_used: number; markdown: string;
}
```

- [ ] **Step 5: Add the client call.** In `web/src/api/client.ts`, add `Depth` to the type import and add this after `peel`:

```ts
  analyze: (address: string, depth: Depth = "quick") => request<{ job_id: string }>("/analyze", post({ address, depth })),
```

- [ ] **Step 6: Add the route.** Replace `Route`, `parseHash` and `routeToHash` in `web/src/lib/route.ts` with:

```ts
export type Route = { view: "graph" } | { view: "kb"; path: string } | { view: "analysis"; address: string };

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  if (h === "kb" || h.startsWith("kb/")) {
    const path = h.slice(3);
    return { view: "kb", path: path ? decodeURIComponent(path) : "index.md" };
  }
  if (h.startsWith("analysis/") && h.length > "analysis/".length) {
    return { view: "analysis", address: decodeURIComponent(h.slice("analysis/".length)) };
  }
  return { view: "graph" };
}

export function routeToHash(route: Route): string {
  if (route.view === "kb") return `#/kb/${route.path}`;
  if (route.view === "analysis") return `#/analysis/${encodeURIComponent(route.address)}`;
  return "#/graph";
}
```

- [ ] **Step 7: Add the store slice.** In `web/src/state/store.ts`:

```ts
import type { AnalysisSections, Depth, JobStatus } from "../api/types";
```

```ts
export interface JobState {
  id: string;
  kind: "trace" | "cluster" | "analysis";
  status: JobStatus;
  nodes: number;
  stops: number;
  error: string | null;
  reason: string | null;
  calls: number | null;
}

export interface AnalysisState { address: string; depth: Depth; sections: AnalysisSections; markdown: string | null }
```

- Add `analysis: AnalysisState | null;` to `Data`.
- Add to `WorkbenchState`:

```ts
  setAnalysis: (analysis: AnalysisState | null) => void;
  patchAnalysis: (patch: Partial<AnalysisState>) => void;
  patchSections: (patch: AnalysisSections) => void;
```

- Add `analysis: null,` to `initial()`.
- Add to the store implementation:

```ts
  setAnalysis: (analysis) => set({ analysis }),
  patchAnalysis: (patch) => set((s) => (s.analysis ? { analysis: { ...s.analysis, ...patch } } : {})),
  patchSections: (patch) =>
    set((s) => (s.analysis ? { analysis: { ...s.analysis, sections: { ...s.analysis.sections, ...patch } } } : {})),
```

- [ ] **Step 8: Add the actions.** In `web/src/state/actions.ts`:

Update the imports:

```ts
import type {
  AnalysisReport, AnalysisSections, Category, Depth, NewTag, RiskLevel, SearchResponse, TracePolicy, TraceSeed,
} from "../api/types";
import { shortAddr } from "../lib/format";
import { navigate } from "../lib/route";
import { type JobState, useWorkbench } from "./store";
```

In `search()`, replace `else if (res.kind === "address") await openAddress(res.query);` with:

```ts
  else if (res.kind === "address") navigate({ view: "analysis", address: res.query });
```

Replace `listen` with:

```ts
function listen(jobId: string, kind: JobState["kind"], onDone?: () => Promise<void>) {
  unsubscribe?.();
  const token = {};
  activeJob = token;
  st().setJob({ id: jobId, kind, status: "running", nodes: 0, stops: 0, error: null, reason: null, calls: null });
  unsubscribe = subscribeJob(jobId, (e) => {
    if (activeJob !== token) return;
    if (e.type === "nodes" || e.type === "edges" || e.type === "stop") {
      st().updateGraph((g) => applyJobEvent(g, e));
      const g = st().graph;
      st().patchJob({ nodes: Object.keys(g.nodes).length, stops: g.stops.length });
    } else if (e.type === "section") {
      st().patchSections({ [e.name]: e.data } as AnalysisSections);
    } else if (e.type === "progress") {
      st().patchJob({ calls: e.calls ?? null, ...(e.size !== undefined ? { nodes: e.size } : {}) });
    } else if (e.type === "done") {
      st().patchJob({ reason: e.reason, calls: e.calls_used });
      if (e.incomplete) st().setMessage(`Partial result: ${e.reason ?? "stopped early"}`);
    } else if (e.type === "status") {
      st().patchJob({ status: e.status, error: e.error });
      unsubscribe = null;
      if (e.status === "done" && onDone) void onDone();
    }
  });
}
```

Append after `startTrace`:

```ts
/** Unsaved work that a new analysis would discard: edits to a saved case or a hand-built graph.
 *  A fresh analysis graph can be regenerated, so it doesn't count. */
export function hasUnsavedWork(): boolean {
  const s = st();
  return s.dirty && (s.caseId !== null || s.analysis === null);
}

/** Run the automatic analysis of an address as a fresh investigation. Returns false when the user
 *  chose to keep their unsaved work. */
export async function startAnalysis(address: string, depth: Depth = "quick"): Promise<boolean> {
  if (hasUnsavedWork() && !window.confirm("Start a new analysis? Unsaved changes to the current investigation will be lost.")) {
    return false;
  }
  detachJob(true);
  st().reset();
  st().setAnalysis({ address, depth, sections: {}, markdown: null });
  const res = await guarded(() => api.analyze(address, depth));
  if (res) {
    const jobId = res.job_id;
    listen(jobId, "analysis", async () => {
      const info = await api.job<AnalysisReport>(jobId).catch(() => null);
      if (info?.result && st().job?.id === jobId) st().patchAnalysis({ markdown: info.result.markdown });
    });
  }
  return true;
}

export async function saveAnalysisAsCase() {
  const s = st();
  if (!s.analysis) return undefined;
  if (!s.caseName.trim()) st().setCaseName(`Analysis of ${shortAddr(s.analysis.address)}`);
  if (!s.notes.trim() && s.analysis.markdown) st().setNotes(s.analysis.markdown);
  return saveCase();
}
```

In `loadCase`, add `st().setAnalysis(null);` directly after `detachJob(true);`, so a loaded case never shows a stale report.

- [ ] **Step 9: Run the tests and the typecheck.**
  - Run: `cd web && npx vitest run && npm run typecheck`
  - Expected: all PASS (53 previously, plus 5 new), typecheck OK.

- [ ] **Step 10: Commit.**

```bash
git add web/src/api web/src/lib/route.ts web/src/lib/route.test.ts web/src/state
git commit -m "feat(web): analysis route, types, API call and store actions" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Web: the report page and entry points

**Files:**
- Create: `web/src/components/AnalysisView.tsx`, `web/src/components/AnalysisView.test.tsx`
- Modify: `web/src/lib/format.ts`, `web/src/lib/format.test.ts` (`formatPct`)
- Modify: `web/src/test/fixtures.ts` (`analysisSections`)
- Modify: `web/src/App.tsx`, `web/src/App.test.tsx`
- Modify: `web/src/components/SearchBar.tsx`, `SearchBar.test.tsx`, `KbBrowser.tsx`, `KbBrowser.test.tsx`
- Modify: `web/src/state/actions.ts` (remove the now-unused `openAddress`)

**Interfaces:**
- Consumes: from Task 8, `startAnalysis`, `cancelJob`, `saveAnalysisAsCase`, `useWorkbench` (`analysis`, `job`, `error`, `select`), `navigate`, and the types.
- Produces:
  - `<AnalysisView address={string} />`: a full-width report page.
  - `formatPct(share: number): string`, e.g. `"67%"` or `"4.0%"`, matching the backend's `pct`.
  - The Analysis nav button in `App`.

- [ ] **Step 1: Add the fixture.** Append to `web/src/test/fixtures.ts` (and add `AnalysisSections` to its type import):

```ts
export const ANALYSED = "bc1qanalysed";
export const RANSOM = "bc1qransom";

export const analysisSections: AnalysisSections = {
  verdict: {
    level: "severe", final: true, low_confidence: false,
    coverage: "Traced 100% of funds to an endpoint within 3 hops; 0.0% not reached",
    reasons: [
      { level: "severe", rule: "direct_severe", text: "Received 0.015 BTC directly from LockBit (ransomware, ransomwhere)" },
      { level: "low", rule: "low_only", text: "Outgoing funds went to only low-risk known entities: Example Exchange" },
    ],
  },
  profile: {
    address: ANALYSED, address_type: "v0_p2wpkh",
    stats: { address: ANALYSED, tx_count: 2, funded_txo_count: 1, funded_sum: 1_500_000, spent_txo_count: 1, spent_sum: 1_500_000, mempool_tx_count: 0, mempool_delta: 0, balance: 0 },
    info: { address: ANALYSED, tags: [], cluster: null, category: null, label: null, risk: "none", stop_category: null },
    txs_seen: 2, history_complete: true, first_seen: 1_700_000_000, last_seen: 1_700_086_400, longest_gap_days: 1,
    received_txs: 1, sent_txs: 1, received_external: 1_500_000, reused: false, behaviour: { peel_step: 1 },
    fingerprint: { signed_txs: 1, signature: "v2|lt:zero|rbf:1|in:v0_p2wpkh", share: 1, traits: {} },
  },
  cluster: { root: ANALYSED, size: 1, partial: false, capped: false, conflicts: [], top_labels: [], calls_used: 1, error: null },
  sources: {
    direction: "backward", total: 1_500_000, resolved_share: 1, incomplete: false, reason: null, calls_used: 3, error: null,
    buckets: [{ kind: "labeled", key: "ransomware", label: "LockBit", risk: "severe", source: "ransomwhere", amount: 1_500_000, share: 1, min_hops: 1, nodes: [`addr:${RANSOM}`] }],
  },
  destinations: {
    direction: "forward", total: 1_500_000, resolved_share: 0.999, incomplete: false, reason: null, calls_used: 4, error: null,
    buckets: [
      { kind: "labeled", key: "exchange", label: "Example Exchange", risk: "low", source: "test", amount: 1_000_000, share: 0.6667, min_hops: 1, nodes: ["addr:bc1qexchange"] },
      { kind: "unspent", key: "unspent", label: "Still unspent", risk: "none", source: null, amount: 499_000, share: 0.3327, min_hops: 1, nodes: ["addr:bc1qunspent"] },
      { kind: "remainder", key: "remainder", label: "Fees or not reached (budget)", risk: "none", source: null, amount: 1_000, share: 0.0007, min_hops: null, nodes: [] },
    ],
  },
};
```

- [ ] **Step 2: Write the failing tests.**

Append to `web/src/lib/format.test.ts` (and add `formatPct` to its import):

```ts
test("formatPct matches the backend report", () => {
  expect(formatPct(0.6667)).toBe("67%");
  expect(formatPct(0.04)).toBe("4.0%");
  expect(formatPct(1)).toBe("100%");
});
```

Create `web/src/components/AnalysisView.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../state/actions", () => ({
  startAnalysis: vi.fn().mockResolvedValue(true), cancelJob: vi.fn(), saveAnalysisAsCase: vi.fn(),
}));

import * as actions from "../state/actions";
import { useWorkbench } from "../state/store";
import { ANALYSED, RANSOM, analysisSections } from "../test/fixtures";
import AnalysisView from "./AnalysisView";

beforeEach(() => {
  useWorkbench.getState().reset();
  vi.mocked(actions.startAnalysis).mockClear();
  window.location.hash = "";
});

function showDone(address = ANALYSED) {
  useWorkbench.getState().setAnalysis({ address, depth: "quick", sections: analysisSections, markdown: "# r" });
  useWorkbench.getState().setJob({ id: "a1", kind: "analysis", status: "done", nodes: 5, stops: 3, error: null, reason: null, calls: 42 });
}

test("starts an analysis for a new address and shows a placeholder", () => {
  render(<AnalysisView address="bc1qnew" />);
  expect(actions.startAnalysis).toHaveBeenCalledWith("bc1qnew");
  expect(screen.getByText(/Starting analysis/)).toBeInTheDocument();
});

test("renders verdict, reasons, profile and exposure tables; rows open the graph", async () => {
  showDone();
  render(<AnalysisView address={ANALYSED} />);
  expect(actions.startAnalysis).not.toHaveBeenCalled();
  const verdict = screen.getByRole("region", { name: "Verdict" });
  expect(within(verdict).getByText(/directly from LockBit/)).toBeInTheDocument();
  expect(within(verdict).getByText(/Traced 100% of funds/)).toBeInTheDocument();
  expect(screen.getByText(/done · 42 API calls/)).toBeInTheDocument();
  const sources = screen.getByRole("region", { name: "Sources of funds" });
  expect(within(sources).getByText("0.015 BTC")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Destinations of funds" })).getByText("67%")).toBeInTheDocument();
  await userEvent.click(within(sources).getByRole("button", { name: "LockBit" }));
  expect(window.location.hash).toBe("#/graph");
  expect(useWorkbench.getState().selected).toBe(`addr:${RANSOM}`);
});

test("buttons: go deeper and save as case", async () => {
  showDone();
  render(<AnalysisView address={ANALYSED} />);
  await userEvent.click(screen.getByRole("button", { name: "Save as case" }));
  expect(actions.saveAnalysisAsCase).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Go deeper" }));
  expect(actions.startAnalysis).toHaveBeenCalledWith(ANALYSED, "deep");
});

test("Open in graph uses the normalised address from the profile", async () => {
  showDone(ANALYSED.toUpperCase());
  render(<AnalysisView address={ANALYSED.toUpperCase()} />);
  await userEvent.click(screen.getByRole("button", { name: "Open in graph" }));
  expect(useWorkbench.getState().selected).toBe(`addr:${ANALYSED}`);
});
```

Replace the last test in `web/src/components/SearchBar.test.tsx` and its mock:

```tsx
vi.mock("../state/actions", () => ({ search: vi.fn() }));
```

```tsx
test("submits on Enter and lists tag hits that open the analysis", async () => {
  (actions.search as ReturnType<typeof vi.fn>).mockResolvedValue({
    kind: "text", query: "lazarus",
    tags: [{ id: 1, address: "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", label: "Lazarus Group", category: "individual", abuse: "sanctioned", actor: null, confidence: "authority_data", confidence_level: 60, source: "s", pack: "ofac_sdn", is_cluster_definer: false, lastmod: null, created_by: "import" }],
  });
  render(<SearchBar />);
  await userEvent.type(screen.getByRole("searchbox"), "lazarus{Enter}");
  expect(actions.search).toHaveBeenCalledWith("lazarus");
  await userEvent.click(await screen.findByRole("button", { name: /Lazarus Group/ }));
  expect(window.location.hash).toBe("#/analysis/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa");
});
```

In `web/src/components/KbBrowser.test.tsx`, change the mock to `vi.mock("../state/actions", () => ({ openTx: vi.fn() }));` and replace the last two lines of the seed test with:

```tsx
  await userEvent.click(await screen.findByRole("button", { name: /analyse bc1qx/i }));
  expect(window.location.hash).toBe("#/analysis/bc1qx");
```

In `web/src/App.test.tsx`, add `vi.mock("./components/AnalysisView", () => ({ default: ({ address }: { address: string }) => <div>Analysis of {address}</div> }));` next to the other component mocks, and append:

```tsx
test("renders the analysis view for an analysis route", () => {
  window.location.hash = "#/analysis/bc1qx";
  renderApp();
  expect(screen.getByText("Analysis of bc1qx")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analysis" })).toBeInTheDocument();
});
```

- [ ] **Step 3: Run them and check they fail.**
  - Run: `cd web && npx vitest run`
  - Expected: the new and changed tests FAIL: `formatPct` is not exported, `./AnalysisView` is missing, the hash is unchanged, and the App shows the graph for the analysis route.

- [ ] **Step 4: Add `formatPct`.** Append to `web/src/lib/format.ts`:

```ts
/** Share (0–1) as a percentage, like the backend report: one decimal below 10%, none above. */
export function formatPct(share: number): string {
  const p = (Number.isFinite(share) ? share : 0) * 100;
  return `${p < 10 ? p.toFixed(1) : p.toFixed(0)}%`;
}
```

- [ ] **Step 5: Create the report page.** Create `web/src/components/AnalysisView.tsx`:

```tsx
import { useEffect } from "react";
import type { Bucket, ClusterSummary, Exposure, Profile, RiskLevel, Verdict } from "../api/types";
import { addrNodeId } from "../graph/model";
import { formatBtc, formatPct, formatTime } from "../lib/format";
import { navigate } from "../lib/route";
import { cancelJob, saveAnalysisAsCase, startAnalysis } from "../state/actions";
import { useWorkbench } from "../state/store";

function openInGraph(nodeId: string | null) {
  navigate({ view: "graph" });
  useWorkbench.getState().select(nodeId);
}

function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className="px-2 py-0.5 rounded text-sm font-semibold uppercase text-white" style={{ background: `var(--risk-${level})` }}>
      {level}
    </span>
  );
}

function Pending({ what, active }: { what: string; active: boolean }) {
  return <p className={`muted text-sm ${active ? "animate-pulse" : ""}`}>{active ? `${what}…` : "Not available."}</p>;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 text-sm py-0.5">
      <span className="muted whitespace-nowrap">{label}</span>
      <span className="text-right break-all">{children}</span>
    </div>
  );
}

function VerdictPanel({ verdict }: { verdict: Verdict }) {
  return (
    <section aria-label="Verdict" className="panel p-4 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <RiskBadge level={verdict.level} />
        {!verdict.final && <span className="muted text-sm">preliminary: tracing still running</span>}
        {verdict.low_confidence && <span className="text-sm" style={{ color: "var(--risk-medium)" }}>low confidence: try Go deeper</span>}
      </div>
      <h2 className="font-semibold">Why</h2>
      <ul className="list-disc pl-5 space-y-1 text-sm">
        {verdict.reasons.map((r, i) => (
          <li key={i}>
            <span className="font-semibold" style={{ color: `var(--risk-${r.level})` }}>{r.level}</span> {r.text}
          </li>
        ))}
      </ul>
      <p className="muted text-sm">{verdict.coverage}</p>
    </section>
  );
}

function ProfilePanel({ p }: { p: Profile }) {
  const fp = p.fingerprint;
  const behaviour = Object.entries(p.behaviour).map(([k, n]) => `${k} ×${n}`).join(", ");
  const tags = p.info.tags.slice(0, 5).map((t) => `${t.label} (${t.abuse ?? t.category})`).join(", ");
  return (
    <section aria-label="Profile" className="panel p-4">
      <h2 className="font-semibold mb-1">Profile</h2>
      <Fact label="Balance">{formatBtc(p.stats.balance)}</Fact>
      <Fact label="Received / sent">{formatBtc(p.stats.funded_sum)} / {formatBtc(p.stats.spent_sum)}</Fact>
      <Fact label="Transactions">{p.stats.tx_count} ({p.txs_seen} analysed)</Fact>
      <Fact label="Active">
        {p.first_seen === null ? "no confirmed activity" : `${formatTime(p.first_seen)}${p.history_complete ? "" : " or earlier"} → ${formatTime(p.last_seen)}`}
      </Fact>
      <Fact label="Longest quiet period">{p.longest_gap_days === null ? "—" : `${p.longest_gap_days} days`}</Fact>
      <Fact label="Address type">{p.address_type ?? "unknown"}{p.reused ? " · reused" : ""}</Fact>
      <Fact label="Labels">{tags || "none"}</Fact>
      <Fact label="Behaviour">{behaviour || "nothing notable"}</Fact>
      <Fact label="Wallet fingerprint">
        {fp.signed_txs ? `${fp.signature} in ${formatPct(fp.share)} of ${fp.signed_txs} signed txs` : "no signed transactions"}
      </Fact>
    </section>
  );
}

function ClusterPanel({ c }: { c: ClusterSummary }) {
  return (
    <section aria-label="Cluster" className="panel p-4">
      <h2 className="font-semibold mb-1">Cluster (co-spent addresses)</h2>
      <Fact label="Size">{c.size} addresses{c.partial ? " (partial)" : ""}{c.capped ? " · capped: large service?" : ""}</Fact>
      <Fact label="Labels">{c.top_labels.length ? c.top_labels.map((t) => `${t.label} ×${t.count}`).join(", ") : "none"}</Fact>
      {c.conflicts.length > 0 && <Fact label="Conflicting labels">{c.conflicts.map((x) => x.labels.join(" / ")).join("; ")}</Fact>}
      {c.error && <p className="text-sm text-[var(--danger)]">Expansion failed: {c.error}</p>}
    </section>
  );
}

function BucketRow({ b }: { b: Bucket }) {
  const category = b.kind === "labeled" ? b.key : b.kind === "own_cluster" ? `${b.key} (own cluster)` : b.kind.replace("_", " ");
  return (
    <tr className="border-t border-[var(--border)]">
      <td className="py-1">
        <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: `var(--risk-${b.risk})` }} />
        {b.nodes.length ? <button className="underline" onClick={() => openInGraph(b.nodes[0])}>{b.label}</button> : b.label}
      </td>
      <td>{category}</td>
      <td className="text-right mono">{formatBtc(b.amount)}</td>
      <td className="text-right">{formatPct(b.share)}</td>
      <td className="text-right">{b.min_hops ?? "—"}</td>
      <td className="pl-3 muted">{b.source ?? "—"}</td>
    </tr>
  );
}

function ExposureTable({ title, e }: { title: string; e: Exposure }) {
  return (
    <section aria-label={title} className="panel p-4">
      <h2 className="font-semibold mb-1">{title}</h2>
      {e.error && <p className="text-sm text-[var(--danger)]">Trace failed: {e.error}</p>}
      {e.buckets.length === 0 ? (
        <p className="muted text-sm">No funds to trace.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="muted text-left">
            <tr>
              <th className="py-1">Where</th><th>Category</th><th className="text-right">Amount</th>
              <th className="text-right">Share</th><th className="text-right">Hops</th><th className="pl-3">Source</th>
            </tr>
          </thead>
          <tbody>{e.buckets.map((b) => <BucketRow key={`${b.kind}-${b.key}-${b.label}`} b={b} />)}</tbody>
        </table>
      )}
      {e.incomplete && e.reason && !e.error && <p className="muted text-xs mt-1">Stopped early: {e.reason}</p>}
    </section>
  );
}

export default function AnalysisView({ address }: { address: string }) {
  const analysis = useWorkbench((s) => s.analysis);
  const job = useWorkbench((s) => s.job);
  const error = useWorkbench((s) => s.error);

  useEffect(() => {
    // startAnalysis sets `analysis` synchronously, so StrictMode's second effect run is a no-op
    if (useWorkbench.getState().analysis?.address === address) return;
    void startAnalysis(address).then((started) => {
      if (!started) navigate({ view: "graph" });
    });
  }, [address]);

  if (!analysis || analysis.address !== address) {
    return <div className="p-4"><Pending what="Starting analysis" active /></div>;
  }
  const { sections } = analysis;
  const running = job?.kind === "analysis" && job.status === "running";
  const pending = running || (!job && !error);
  const status = running ? `analysing… ${job?.calls ?? 0} API calls`
    : job?.status === "done" ? `done · ${job.calls ?? 0} API calls`
    : job?.status === "error" ? `failed: ${job.error}`
    : job?.status ?? (error ? `failed: ${error}` : "");
  const seed = addrNodeId(sections.profile?.address ?? address);
  return (
    <div className="h-full overflow-auto">
      <div className="max-w-5xl mx-auto p-4 space-y-4">
        <header className="flex flex-wrap items-center gap-3">
          <h1 className="mono text-lg break-all">{address}</h1>
          <button className="btn" onClick={() => void navigator.clipboard?.writeText(address)}>Copy</button>
          <span className="muted text-sm">{analysis.depth} analysis{status ? ` · ${status}` : ""}</span>
          <div className="ml-auto flex flex-wrap gap-2">
            {running && <button className="btn" onClick={() => void cancelJob()}>Cancel</button>}
            <button className="btn btn-primary" onClick={() => openInGraph(seed)}>Open in graph</button>
            <button className="btn" disabled={running || analysis.depth === "deep"} onClick={() => void startAnalysis(address, "deep")}>Go deeper</button>
            <button className="btn" disabled={!analysis.markdown} onClick={() => void saveAnalysisAsCase()}>Save as case</button>
          </div>
        </header>
        {sections.verdict ? <VerdictPanel verdict={sections.verdict} /> : <Pending what="Checking labels" active={pending} />}
        <div className="grid gap-4 md:grid-cols-2">
          {sections.profile ? <ProfilePanel p={sections.profile} /> : <Pending what="Loading profile" active={pending} />}
          {sections.cluster ? <ClusterPanel c={sections.cluster} /> : <Pending what="Expanding cluster" active={pending} />}
        </div>
        {sections.sources ? <ExposureTable title="Sources of funds" e={sections.sources} /> : <Pending what="Tracing where the funds came from" active={pending} />}
        {sections.destinations ? <ExposureTable title="Destinations of funds" e={sections.destinations} /> : <Pending what="Tracing where the funds went" active={pending} />}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Wire up `App`.** In `web/src/App.tsx`:
  - Add `import AnalysisView from "./components/AnalysisView";`.
  - Add `const lastAnalysis = useWorkbench((s) => s.analysis?.address ?? null);` after the `caseName` selector.
  - Insert this nav button between Graph and Knowledge base:

```tsx
          <button
            className={`btn ${route.view === "analysis" ? "btn-primary" : ""}`}
            disabled={!lastAnalysis && route.view !== "analysis"}
            title={lastAnalysis ? "" : "Search an address to analyse it"}
            onClick={() => lastAnalysis && navigate({ view: "analysis", address: lastAnalysis })}
          >
            Analysis
          </button>
```

  - Replace the `{route.view === "kb" ? (<KbBrowser path={route.path} />) : (` branch opener with:

```tsx
        {route.view === "kb" ? (
          <KbBrowser path={route.path} />
        ) : route.view === "analysis" ? (
          <AnalysisView address={route.address} />
        ) : (
```

- [ ] **Step 7: Point the search hits and KB seeds at the analysis page.** In `web/src/components/SearchBar.tsx`:
  - Change the import to `import { search } from "../state/actions";` and add `import { navigate } from "../lib/route";`.
  - Replace `void openAddress(t.address);` with `navigate({ view: "analysis", address: t.address });`.

In `web/src/components/KbBrowser.tsx`:
  - Change the import to `import { openTx } from "../state/actions";`.
  - Replace the seed `<button …>Open in graph</button>` with:

```tsx
                  <button
                    className="btn"
                    aria-label={s.kind === "tx" ? `open ${s.value} in graph` : `analyse ${s.value}`}
                    onClick={() => {
                      if (s.kind === "tx") {
                        navigate({ view: "graph" });
                        void openTx(s.value);
                      } else {
                        navigate({ view: "analysis", address: s.value });
                      }
                    }}
                  >
                    {s.kind === "tx" ? "Open in graph" : "Analyse"}
                  </button>
```

In `web/src/state/actions.ts`:
  - Delete the now-unused `openAddress` export.
  - Remove `addNodes` and `addressNode` from the `../graph/model` import. Only `openAddress` used them; `noUnusedLocals` would fail otherwise.

- [ ] **Step 8: Run the tests and the typecheck.**
  - Run: `cd web && npx vitest run && npm run typecheck`
  - Expected: all PASS, typecheck OK.

- [ ] **Step 9: Commit.**

```bash
git add web/src
git commit -m "feat(web): analysis report page; address search, tag hits and KB seeds open it" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: End-to-end test, README and real-chain check

**Files:**
- Modify: `web/e2e/fixtures.ts`, `web/e2e/workbench.spec.ts`
- Modify: `README.md` ("Web workbench" section)

**Interfaces:**
- Consumes: everything above. The e2e test imports `analysisSections` and `ANALYSED` from `web/src/test/fixtures.ts`.
- Produces: an e2e test, `entering an address runs the automatic analysis and opens its graph`.

- [ ] **Step 1: Extend the API mock.** In `web/e2e/fixtures.ts`:
  - Add `import { ANALYSED, analysisSections } from "../src/test/fixtures";`.
  - Add these constants above `mockApi`:

```ts
export const ADDRESS = ANALYSED;
const ANALYSIS_EVENTS = [
  { type: "section", name: "profile", data: analysisSections.profile },
  { type: "section", name: "verdict", data: { ...analysisSections.verdict, final: false } },
  { type: "nodes", items: [
    { id: `addr:${ANALYSED}`, kind: "address", label: "bc1qanal…ysed", data: {} },
    { id: `tx:${TXID}`, kind: "tx", label: "aaaaaaaa", data: {} },
    { id: "addr:bc1qransom", kind: "address", label: "LockBit", data: { risk: "severe" } },
  ] },
  { type: "edges", items: [
    { id: `in:${TXID}:0`, source: "addr:bc1qransom", target: `tx:${TXID}`, value: 2_000_000, taint: 1_500_000 },
    { id: `out:${TXID}:0`, source: `tx:${TXID}`, target: `addr:${ANALYSED}`, value: 1_500_000, taint: 1_500_000 },
  ] },
  { type: "stop", item: { node: "addr:bc1qransom", reason: "labeled", taint: 1_500_000, detail: "ransomware: LockBit", hops: 1 } },
  { type: "section", name: "cluster", data: analysisSections.cluster },
  { type: "section", name: "sources", data: analysisSections.sources },
  { type: "section", name: "destinations", data: analysisSections.destinations },
  { type: "section", name: "verdict", data: analysisSections.verdict },
  { type: "done", incomplete: false, reason: null, calls_used: 42 },
  { type: "status", status: "done", error: null },
];
```

  - Replace the `/search` line in the route handler, and add the analysis routes after it:

```ts
    if (path === "/search") {
      const query = url.searchParams.get("q")!;
      return json(route, /^[0-9a-f]{64}$/i.test(query) ? { kind: "txid", query: query.toLowerCase() } : { kind: "address", query });
    }
    if (path === "/analyze" && method === "POST") return json(route, { job_id: "an1" }, 202);
    if (path === "/jobs/an1/events") {
      const body = ANALYSIS_EVENTS.map((e, seq) => `data: ${JSON.stringify({ seq, ...e })}\n\n`).join("");
      return route.fulfill({ status: 200, contentType: "text/event-stream", body });
    }
    if (path === "/jobs/an1") {
      return json(route, { id: "an1", kind: "analysis", status: "done", error: null, events: ANALYSIS_EVENTS.length, result: { markdown: `# Address analysis: ${ANALYSED}\n` } });
    }
```

- [ ] **Step 2: Write the e2e test.** Append to `web/e2e/workbench.spec.ts` (and import `ADDRESS` from `./fixtures`):

```ts
test("entering an address runs the automatic analysis and opens its graph", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("searchbox").fill(ADDRESS);
  await page.getByRole("searchbox").press("Enter");
  await expect(page).toHaveURL(new RegExp(`#/analysis/${ADDRESS}$`));
  const verdict = page.getByRole("region", { name: "Verdict" });
  await expect(verdict.getByText(/directly from LockBit/)).toBeVisible();
  await expect(verdict.getByText("preliminary: tracing still running")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Destinations of funds" }).getByRole("button", { name: "Example Exchange" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save as case" })).toBeEnabled();
  await page.getByRole("button", { name: "Open in graph" }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText("1 txs · 2 addresses · 2 edges · 1 stops");
});
```

- [ ] **Step 3: Run the e2e tests.**
  - Run: `cd web && npm run e2e`
  - Expected: 3 passed, including the existing txid and case test, which still gets `kind: "txid"` for its 64-hex query.

- [ ] **Step 4: Update the README.** In `README.md` under "## Web workbench", replace the first bullet (`- Search a txid, …`) with:

```markdown
- Enter an address to get an **automatic analysis**: a risk verdict with the reasons behind it, where the
  funds came from and went to (exchanges, mixers, sanctioned or ransomware addresses, unspent), the
  co-spend cluster and the wallet fingerprint. It fills in live in about 1–1.5 minutes on public APIs;
  **Go deeper** reruns it with larger budgets (5–10 min) and **Open in graph** shows the traced paths.
  The same report on the command line: `uv run btcintel analyze <address> [--deep] [--json]`.
- Search a txid or `txid:vout` to open it in the graph, or a tag name to find labeled addresses.
```

- [ ] **Step 5: Run the full automated verification.**
  - Run: `cd backend && uv run pytest -q && uv run ruff check . && cd ../web && npm test && npm run typecheck && npm run e2e`
  - Expected: everything passes.

- [ ] **Step 6: Check against the real chain** (manual; uses the imported tags in `data/intel.db`). Pick an OFAC-listed and a ransomwhe.re address:

```bash
cd /home/fancybear/btc-intel && python3 -c "
import sqlite3; c = sqlite3.connect('file:data/intel.db?mode=ro', uri=True)
for pack in ('ofac_sdn', 'ransomwhere'):
    print(pack, c.execute('select address from tags where pack=? limit 1', (pack,)).fetchone()[0])"
```

Then run, from `backend/`, each with `time`:
- `uv run btcintel analyze <ofac address>`. Expect verdict SEVERE with an `own_label` reason.
- `uv run btcintel analyze <ransomwhere address>`. Expect SEVERE, with a destinations table that is not empty.
- `uv run btcintel analyze bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h`, a well-known Binance cold wallet (or any exchange-tagged address from `select address from tags where category='exchange' limit 1`). Expect low or none, with "capped: likely a large service" or a large cluster.

For each run, check that the quick analysis finishes in about 1–1.5 minutes. Then build the web app (`cd web && npm run build`), run `uv run btcintel serve`, open http://127.0.0.1:8765, paste one of the addresses into the search box, and watch the preliminary verdict appear within seconds and the sections fill in live. Record the timings in the task report.

- [ ] **Step 7: Commit.**

```bash
git add web/e2e README.md
git commit -m "test(web): e2e for the automatic address analysis; document it in the README" \
  -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
