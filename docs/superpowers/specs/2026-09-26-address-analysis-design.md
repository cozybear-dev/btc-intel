# Automatic Address Analysis — Design Spec

- **Date:** 2026-09-26
- **Status:** Approved design (brainstorming + plan review); next step is the implementation plan
- **Builds on:** [2026-09-25-btc-intel-design.md](2026-09-25-btc-intel-design.md) (an early slice of Phase 2 "risk screening")

## Context

The workbench is too hands-on. Searching an address today (`web/src/state/actions.ts:57` `openAddress`) adds one bare node and nothing else: no expansion, no trace, no cluster, and no findings for addresses. Every step is a manual right-click. The building blocks exist but nothing chains them:
- label and risk lookup (`labels/lookup.py`)
- forward and backward trace (`trace/engine.py`)
- CIOH cluster expansion (`cluster/expand.py`)
- tx flags and fingerprint (`heuristics/flags.py`, `heuristics/fingerprint.py`)
- about 800k imported tags (OFAC, ransomwhe.re, GraphSense packs)

**Goal:** the user enters a BTC address and automatically gets an initial analysis answering four questions: *Is it risky? Where did the funds come from? Where did they go? Who is behind it?*

**Agreed in brainstorming:**
- **Timing:** fast results first, deeper on demand. Labels and profile arrive in seconds, a bounded pass of about 1–1.5 minutes fills in live, and a "Go deeper" button reruns with larger budgets.
- **Presentation:** a readable full-width report page first. The graph is built in the background for drill-down.
- **Architecture:** Approach A, one backend `analysis` job on the existing job manager and SSE stream, plus a CLI command.
- **Budget assumption:** the user runs on public Esplora APIs (no `.env`; about 5 req/s combined).

**Two existing problems the design must fix:**
1. `LabelLookup.stop_category` matches only `tag.category`. About 86k risky tags have `category=unknown` and carry the risk in `abuse` (ransomware, extortion, theft, scam, terrorism), so traces pass through them.
2. A forward trace from an address that is already labeled stops immediately at the seed (`engine.py:119-127` `follow()` label-checks the seed's own outputs). Analyzing a known-bad address would therefore show no destinations.

## Pipeline (backend)

`POST /api/analyze {address, depth: "quick"|"deep"}` returns 202 `{job_id}`; an invalid address returns 400 via `valid_address`. The job kind is `analysis`.

**Stages:**
1. **Profile (about 5 calls, a few seconds).**
   - `chain.get_address` stats.
   - Up to N history txs via `chain.iter_address_txs`. The tx bodies get cached, so the traces reuse them for free.
   - `labels.lookup` for own and cluster-inherited tags, plus `uf.meta`.
   - Activity: first and last seen (marked "≥" when history is truncated), longest dormancy gap, address reuse, and address type via `chain/validate.py address_type`.
   - Behavior counts from `tx_flags` across history: coinjoin:*, peel_step, fan-out, consolidation, xchain.
   - Wallet fingerprint summary over the txs this address signed, using `fingerprint(tx).signature()` and traits: the dominant signature and its consistency %. No wallet-name guessing.
   - Emits the `profile` section and a **preliminary verdict** (label rules only).
2. **Cluster, backward trace and forward trace run concurrently** (`asyncio.gather`). Each keeps its own `CallBudget` scope; budgets live in ContextVars, so this is safe across tasks.
   - `expand_cluster(...)` produces the `cluster` section: size, partial, capped ("large service?"), conflicts and top `cluster_tags`.
   - The traces use `taint_model="haircut"`, and `stop_categories` is set to all taxonomy ids except `unknown`, which now match `abuse` as well as `category`.
   - Trace `nodes`/`edges`/`stop` events are forwarded into the job, so the web graph is already built.
3. **Exposure** runs per direction over each `TraceResult`. Its output feeds the `sources` and `destinations` sections.
4. **Final verdict and report.** The job result is `AnalysisReport.model_dump()`, including a `markdown` rendering.

**Budgets:**

| Depth | History | Each trace | Cluster | Total | Time on public APIs |
|---|---|---|---|---|---|
| quick | 100 txs | 3 hops, 60 txs, 120 calls | 200 addresses, 60 calls | about 300 calls | about 1–1.5 min |
| deep | 500 txs | 6 hops, 300 txs, 600 calls | 2000 addresses, 400 calls | about 1,600+ calls | about 5–10 min |

Both traces use `min_value_sats=10_000` and set `max_address_txs` to the history size.

**Job events** (on top of the existing trace events and the final `status`):
- `{"type":"section","name":"profile|cluster|sources|destinations|verdict","data":{…}}`. The verdict is sent twice: preliminary, then final.
- `{"type":"progress","stage":…,"calls":…}`
- `{"type":"done","incomplete","reason","calls_used"}`

**Engine and label changes** (small, and backward compatible for default traces):
- `labels/lookup.py`: the stop match also considers `t.abuse`. `stop_category` returns the abuse id when that is what matched. Default stop sets contain no abuse ids, so existing trace behavior is unchanged.
- `trace/engine.py`: never label-stop at the seed address itself, in either direction. `Stop` records `hops`, the hop count at which the stop happened.
- `trace/graph.py`: add `Stop.hops: int | None = None`.

## Exposure (`analysis/exposure.py`)

Stops are grouped into buckets. Each bucket records amount (sats), share of the traced total, the smallest hop count and example addresses.
- **Labeled:** keyed by (abuse, else category) plus label, with risk and tag source taken from the node's label data.
- **CoinJoin:** keyed by kind.
- **Unspent:** forward only.
- **Newly mined:** coinbase, backward only.
- **Beyond limits:** max_hops, min_value or max_txs.
- **Not reached (budget):** the total minus all stops.
- **Own cluster:** a labeled stop whose address is in the seed's cluster (checked via `uf.find`). It is reported separately, not as exposure.

The traced total is the sum of the seed's received outputs within the fetched history. Buckets always add up to 100%.

## Verdict (`analysis/verdict.py`)

Levels come from `catalog.schema.RISK_ORDER`: none < low < medium < high < severe. The verdict is the highest level any rule fires. Reasons are sorted worst first, and each gives the amount, share, hops, label and source. Thresholds are named constants.

| # | Rule | Level |
|---|---|---|
| 1 | Own tag with risk ≥ medium | that risk |
| 1b | Tag inherited from the cluster | that risk, marked "via cluster (N addrs)"; one level lower if the cluster has label conflicts |
| 2 | 1-hop flow to or from a severe entity | severe |
| 3 | ≥ 10% of traced value (either direction) involves high or severe entities | high |
| 3b | > 0% and < 10% involves high or severe entities | medium |
| 4 | ≥ 25% involves medium entities (CoinJoin, gambling, instant exchange, bridge…) | medium |
| 5 | Only low or none labeled entities reached | low |
| 6 | Nothing labeled reached | none |

A **coverage line** is always shown: the share of value traced to an endpoint versus the share not reached. When more than 50% was not reached, the verdict is marked "low confidence — try Go deeper".

## Backend files

New package `backend/btcintel/analysis/`:
- `__init__.py`
- `models.py`: `AnalysisPolicy` with `quick()` / `deep()`, `Profile`, `ClusterSummary`, `Bucket`, `Exposure`, `Verdict`, `AnalysisReport`
- `profile.py`: pure aggregation over `AddressStats` and a list of `Tx`
- `exposure.py`: pure, over a `TraceResult` plus a self-cluster predicate
- `verdict.py`: pure rules
- `report.py`: `to_markdown(report)`
- `run.py`: `async analyze_address(address, policy, *, chain, tags, uf, taxonomy, emit=None) -> AnalysisReport`, the orchestration. It builds its own `LabelLookup` instances: a fresh one after the cluster stage for the final label rules, and the analysis stop set for the traces.

Other backend changes:
- New `backend/btcintel/api/routes_analysis.py` with `POST /api/analyze`, registered in `api/app.py` next to the other routers.
- `backend/btcintel/cli.py`: `analyze <address> [--deep] [--json]` prints the Markdown (or JSON), following the existing `trace` command pattern.
- Modified: `trace/engine.py`, `trace/graph.py`, `labels/lookup.py`.

**Reused as-is:**
- `JobManager.start` (`jobs/manager.py:38`)
- `trace()` / `TracePolicy` / `TraceSeed` (`trace/engine.py`)
- `expand_cluster` / `ExpandPolicy` / `cluster_tags` / `cluster_conflicts` (`cluster/expand.py`)
- `tx_flags` (`heuristics/flags.py`) and `fingerprint` (`heuristics/fingerprint.py`)
- `AppState.labels()` (`runtime.py:42`)
- `Taxonomy.risk` / `risk_of_tag`
- `address_type` (`chain/validate.py`)
- the per-address `delta` computation from `tx_summary` (`api/routes_chain.py:21`), which `profile.py` reimplements as a small helper for received and sent counts

## Web

- **Route:** in `web/src/lib/route.ts`, add `{ view: "analysis"; address: string }` for `#/analysis/<address>`.
- **Nav:** `web/src/App.tsx` gets an **Analysis** nav button and renders `AnalysisView` for that route.
- **Search:** in `web/src/state/actions.ts`, `search()` navigates address results to the analysis route. Tag hits in `SearchBar` and KB incident address seeds (`KbBrowser`) do the same. Transaction searches still open the graph.
- **Store** (`web/src/state/store.ts` and `actions.ts`):
  - `JobState.kind` gains `"analysis"`.
  - A new `analysis` slice holds `{address, depth, sections, verdict}`.
  - `startAnalysis(address, depth)` asks for confirmation if the graph is dirty, then `detachJob(true)` and `reset()` as `newCase` does, then `api.analyze`, then `listen(…, "analysis")`.
  - `listen()` also handles `section` events. Graph and stop events still go through `applyJobEvent`.
- **API client:** `web/src/api/client.ts` gets `analyze(address, depth)`; `web/src/api/types.ts` gets the report and section types plus the `section` job event.
- **New `web/src/components/AnalysisView.tsx`:**
  - Header: address with copy, verdict badge (risk tokens `--risk-*`), live "analysing · N calls", Cancel.
  - "Why" reasons and the coverage line.
  - Sections: Profile, Cluster, Sources and Destinations tables, with skeletons until each arrives.
  - Clicking a bucket row goes to the graph with that node selected.
  - Buttons: **Open in graph**, **Go deeper**, and **Save as case**. Save as case names the case "Analysis of <addr>" and puts the report Markdown into empty notes.
  - Reloading the route reruns the quick analysis, which is mostly cached. No new server storage.
- **README:** update "Web workbench" and add the new CLI command.

## Verification

- **Backend** (`cd backend && uv run pytest`), using TDD with the existing `FakeChain`, `mk_tx`, `build_scenario` and `make_client`/`wait_job` fixtures. New tests go in `tests/analysis/`:
  - profile aggregation
  - exposure buckets: sum to 100%, own cluster, not reached
  - one test per verdict rule
  - end-to-end `analyze_address` on `build_scenario()`
- **Engine and label regressions:**
  - a labeled seed doesn't stop at itself
  - `Stop.hops` is set
  - abuse-only tags stop analysis traces
  - default traces are unchanged
- **API and CLI:** an API test for `POST /api/analyze` (sections streamed over SSE, final result) and a CLI test.
- **Lint:** `uv run ruff check`.
- **Web** (`cd web && npm test && npm run typecheck && npm run e2e`):
  - route parsing
  - search sending an address to analysis
  - store handling of section and graph events
  - `AnalysisView` rendering a fixture report
  - Playwright: mock `/api/analyze` plus SSE, the report renders, Open in graph shows the nodes (extend `web/e2e/fixtures.ts` `mockApi`)
- **Manual:** run `uv run btcintel serve` plus the web app, then analyze:
  - an OFAC-listed address: severe within seconds
  - a ransomwhe.re address: severe, with destinations shown
  - an exchange deposit address: low, cluster capped as "large service?"
  - Also run `btcintel analyze <addr>` and check the quick run finishes in about 1–1.5 minutes on the public APIs.

## Process after approval

Work happens on a new branch `feat/address-analysis` off `main`. It is independent of the unmerged Docker branch.

1. This design is saved as `docs/superpowers/specs/2026-09-26-address-analysis-design.md`.
2. Invoke **superpowers:writing-plans** to produce the task-level implementation plan in `docs/superpowers/plans/`.
3. You review that plan and choose the execution method.
