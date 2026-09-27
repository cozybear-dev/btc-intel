# btc-intel Design Spec

- **Date:** 2026-09-25
- **Status:** Approved design (brainstorming); awaiting spec review before implementation planning
- **Scope of first implementation plan:** Phase 0 (knowledge base) + Phase 1 (tracing workbench MVP)

## Context

Goal: an open-source alternative to Chainalysis (Reactor + KYT) for Bitcoin. It has three jobs:
1. **Incident tracing**: start from a hack, ransom, or theft address or tx and follow the funds through hops, mixers, peel chains and swaps to cash-out points.
2. **Risk screening**: for any address or tx, show its exposure to known-bad entities and explain the score.
3. **Whole-chain intel**: cluster the entire chain into entities and label them. This comes later and needs a local node plus ~2 TB of disk.

Decisions made in brainstorming:
- **Own stack.** Python engine plus a React workbench. GraphSense was rejected because it needs a full node, Cassandra and Spark before anything works.
- **Public Esplora APIs first** (mempool.space, blockstream.info), with a pluggable source so a self-hosted Esplora or bitcoind can be swapped in later.
- **The main UI is a Reactor-style web graph workbench.**

Machine: 12 cores, 15 GB RAM, ~914 GB free disk, Python 3.13, Node 20.19, Docker, git. uv, a Bitcoin node and Tor are not installed.

The empty project dir is `/home/fancybear/btc-intel`.

Defaults (accepted at plan approval):
- **Bitcoin only.** Cross-chain exits (THORChain, Chainflip, bridges, instant swappers) are detected and labeled at the BTC boundary but not followed onto ETH or Tron.
- **Apache-2.0 license.**
- **Local-only server** (binds 127.0.0.1, no auth in the MVP).

---

## Research summary (becomes the Phase 0 knowledge base and drives the detectors)

### A. Analysis techniques (heuristic catalog, IDs `H-*`)
| ID | Technique | Signal / notes | Key refs |
|---|---|---|---|
| H-CIOH | Common-input-ownership | All inputs of a tx belong to one entity. **Disabled** on coinjoin/payjoin/multi-party txs | Nakamoto 2008 §10; Reid & Harrigan 2011; Meiklejohn et al. 2013 |
| H-REUSE / H-PUBKEY | Address and pubkey reuse | Same address, or the same pubkey across P2PKH/P2WPKH/P2SH-wrapped forms and multisig scripts, links activity (e.g. cosigner keys shared across exchange multisigs) | — |
| H-CHG-* | Change detection (weighted votes) | Fresh vs. previously seen output address; script type matches the inputs; round payment amount vs. non-round change; unnecessary-input / optimal-change; self-change back to an input address (definitive); value precision; output position/BIP69; fingerprint continuity of the spending tx; one-output sweeps = self-transfer | Meiklejohn 2013; Kappos et al. 2022 "How to Peel a Million"; Möser & Narayanan 2022 (ML change detection) |
| H-FP | Wallet fingerprinting | nVersion (1/2/3), nLockTime (0 vs. anti-fee-sniping tip height), nSequence (final / RBF 0xfffffffd), low-R signature grinding, input/output ordering, fee-rate rounding, script types and mixing, uncompressed keys, BIP67 sorted multisig, taproot key- vs. script-path | Misra 2024 (30+ traits, ~50% single-tx wallet ID); Corral Urbano/DISCRYPT; DFRWS 2025 "Tumbling down the stairs" |
| H-PEEL | Peel-chain following | 1-in/2-out, one large + one small output, the large one repeatedly re-peeled; auto-follow the change | Kappos 2022 |
| H-MOTIF | Graph motifs | Fan-out (dispersal), fan-in (consolidation), deposit-address sweeps (exchange deposit clusters), round-tripping, rapid multi-address sweeps (weak-key theft) | — |
| H-CJ-* | CoinJoin detection | Wasabi 1.x (ZeroLink ~0.1 BTC levels + coordinator fee); Wasabi 2.x/WabiSabi (≥50 inputs, standard denomination set, P2WPKH/P2TR only); Whirlpool Tx0 + mix (equal in/out count 5–8, all outputs = pool denomination); JoinMarket (n equal outputs + ≤n change, fidelity-bond timelocked P2WSH); Stonewall/Stonewall-X2 (4 outputs, 2 equal); generic equal-output | crocs-muni/coinjoin-analysis + Dumplings rules; PoPETs 2026 CoinJoin ecosystem paper |
| H-CJ-POST | Post-mix demixing | Consolidating several mixed outputs together, toxic (unmixed) change, remix graph, timing, address reuse after the mix, subset-sum ("CoinJoin Sudoku") on non-equal joins, Boltzmann link-probability entropy | Atlas 2014; Maurer et al. 2017; LaurentMT Boltzmann/KYCP |
| H-XCHAIN | Cross-chain exit markers | THORChain OP_RETURN memos (`=:ETH.ETH:0x…` reveals the destination chain and address); known vaults of Chainflip, bridges (BTC.b, WBTC, tBTC) and instant swappers; Liquid peg-in/peg-out; Lightning channel funding/close (2-of-2 P2WSH, P2TR simple channels) | — |
| H-CORR | Amount/time correlation | Value in ≈ value out − fee within a time window, to demix custodial mixers and swappers; fiat-round amounts via historical price | — |
| H-COINBASE | Miner attribution | Coinbase scriptSig tags and payout addresses (mempool `mining-pools` data) | — |
| H-TEMPORAL | Timezone / behavior profiling | Hour-of-day histograms, dormancy then sudden movement | — |
| H-TAINT | Taint models | Poison, haircut (default), FIFO (per-tx value-range mapping), TIHO | Anderson et al. 2018; Tironsakkul et al. 2019; Möser, Böhme & Breuker 2014 |
| H-OSINT | Off-chain attribution | Court filings, OFAC SDN, exchange proof-of-reserves address lists, ransom notes, forums, and "interaction" (making deposits to learn service addresses) | Meiklejohn 2013 |
| — (KB only) | Network-layer deanonymization | First-relay IP analysis; Dandelion/Tor mitigations. Not on-chain, so out of scope for the code | Biryukov et al. 2014; Koshy et al. 2014 |

### B. Obfuscation and laundering techniques (catalog, IDs `O-*`, mapped to OAK `OAK-T7.xxx` and FATF red flags where they exist)
1. **Custodial mixers**: Bitcoin Fog, Helix, ChipMixer (0.001·2ⁿ "chips", taken down 2023), Blender.io and Sinbad (both sanctioned), Cryptomixer (€1.3B processed, taken down Dec 2025 in Operation Olympia). Detect with deposit-cluster labels, payout patterns, amount/time correlation and fingerprint mismatch.
2. **Non-custodial CoinJoin**: Wasabi 2.x on community coordinators after zkSNACKs shut in Jun 2024 (kruw.io ≈99% of 2025–26 volume); Whirlpool revived by Ashigaru in Jun 2025; JoinMarket (original repo archived Apr 2026; joinmarket-ng and Jam continue).
3. **Steganographic transactions that break CIOH**: PayJoin (BIP78, and BIP77 async), Stowaway, Stonewall/Stonewall-X2, Ricochet (extra hops to defeat shallow exchange screening).
4. **Peel chains and layering** through thousands of fresh addresses (Bitfinex 2016, ransomware affiliates).
5. **Dispersal and structuring**: splitting into many small uniform amounts (Bybit BTC dispersed to ~11,000 addresses).
6. **Dormancy and slow laundering**: years-long waits (Silk Road/Zhong, Bitfinex, LuBian). About 50% of 2025 stolen funds were still unspent.
7. **Chain hopping**: THORChain, Chainflip, instant exchangers (eXch, shut Apr 2025; FixedFloat; SideShift; ChangeNOW), bridges, and swaps to Monero (the Aug 2024 $243M and Apr 2025 $330M social-engineering thefts).
8. **L2 and off-chain**: Lightning (private channels, submarine swaps), Liquid confidential transactions, Fedimint/Cashu ecash, Ark.
9. **Nested services, OTC and P2P**: nested VASPs, OTC brokers, P2P markets (Bisq, HodlHodl, RoboSats), guarantee marketplaces (Huione), high-risk exchanges (BTC-e, Garantex→Grinex, Bitzlato), darknet markets used as mixers (AlphaBay in Bitfinex), gambling, ATMs, gift cards.
10. **Protocol privacy features**: Taproot (multisig looks single-sig), Silent Payments (BIP352), BIP47 PayNyms, change avoidance via exact-amount coin selection, script-type mimicry to defeat change heuristics, fingerprint mimicry.
11. **Weak-key mass sweeps** as a theft vector: LuBian 2020 (~127k BTC, later forfeited by the US DOJ in Oct 2025 as Prince Group funds), Milk Sad 2023, and the Coldcard Mk3 flaw of Jul 2026 (~1,082 BTC swept from 1,196 addresses in 41 min).

### C. Major incidents: TTP case studies (each gets a KB page plus a YAML of public seed txids/addresses cited to primary sources)
| Incident | Vector | Laundering TTPs observed |
|---|---|---|
| Mt. Gox 2011–14 (~650–850k BTC) | Long-running hot-wallet key theft | Slow drain; cash-out through a complicit exchange (BTC-e/Vinnik) |
| Silk Road/Zhong 2012 (50,676 BTC) | Withdrawal-bug exploit, 140+ rapid withdrawals | Many accounts, ~9 yr dormancy, consolidation; caught via exchange KYC |
| Bitfinex 2016 (119,754 BTC) | Multisig platform compromise, ~2,000 txs | Peel chains, thousands of addresses, automated txs, AlphaBay used as a mixer, chain hopping, fake-ID exchange accounts; ~94k BTC recovered in 2022 |
| Colonial Pipeline 2021 (75 BTC) | Ransomware (DarkSide) | Affiliate/operator split and hop chain; FBI traced and seized 63.7 BTC |
| Lazarus 2022–23 (Ronin, Harmony, Atomic) | Key/infra compromise (ETH origin) | Tornado → renBridge/Avalanche bridge → BTC → Blender/Sinbad/ChipMixer → OTC |
| DMM Bitcoin 2024 (4,502.9 BTC) | TraderTraitor social engineering | Mixer → THORChain/Avalanche/Threshold → USDT on Tron → Huione Guarantee |
| Bybit 2025 ($1.46B ETH) | Safe{Wallet} UI supply-chain attack | ETH→BTC via THORChain/Chainflip/eXch in 10 days; BTC dispersed to ~11k addresses; OTC |
| $243M (2024) / $330M (2025) social-engineering thefts | Victim social engineering | Instant exchangers → Monero |
| Coldcard Mk3 weak seeds (Jul 2026) | Low-entropy seeds (~40-bit) | Batched sweeps of dormant single-sig addresses |
| Liquid federation (Sep 2026, ~4,000 BTC) | Elements bug minted unbacked L-BTC → SideSwap → peg-out | "White-hat" negotiation; ~3,400 BTC returned |
| Bitget (24 Sep 2026, $351.6M) | Hot-wallet compromise, Lazarus suspected (unconfirmed) | **Live case.** A useful first real investigation if BTC is involved |

Common playbooks to encode as TTP chains:
- **DPRK:** theft → swap to native asset → bridge to BTC → mixer/CoinJoin → peel/disperse → OTC → USDT on Tron → fiat.
- **Ransomware:** fresh address → affiliate split → mixer or high-risk exchange or instant swapper → cash-out.

### D. Open data to import
- GraphSense public TagPacks (YAML, MIT)
- OFAC SDN XML (XBT addresses; ~1,000 crypto addresses as of Sep 2026)
- mempool `mining-pools` pools JSON
- ransomwhe.re export
- Exchange proof-of-reserves address lists
- Curated incident seeds from DOJ/FBI filings
- Optional connector: Chainabuse (needs an API key)

Also reuse the ai-decisions/openlabels TagPack tooling (Apache-2.0) if it fits.

---

## Architecture

```
btc-intel/
  docs/kb/            research knowledge base (markdown): heuristics/, obfuscation/, incidents/, ttp-matrix.md, references.md
  catalog/            machine-readable, drives code + UI: heuristics.yaml, techniques.yaml, categories.yaml, incidents/*.yaml, tagpacks/
  backend/btcintel/   Python 3.13 package (uv, FastAPI, httpx[socks], pydantic v2, sqlite3)
    chain/            models.py (Tx/TxIn/TxOut/Address), source.py (ChainSource Protocol), esplora.py, cache.py, ratelimit.py, validate.py
    heuristics/       base.py (Finding: id, subject, label, confidence, evidence), registry.py, cioh.py, change.py,
                      fingerprint.py, coinjoin.py, patterns.py (peel/fan-in/fan-out/sweep/round), crosschain.py (THORChain memos, vault tags)
    cluster/          unionfind.py (SQLite-persisted), expand.py (capped cluster expansion; coinjoin-aware; supercluster guard)
    labels/           store.py, taxonomy.py, tagpack.py (import/export GraphSense format), ofac.py, pools.py, ransomwhere.py
    trace/            engine.py (priority expansion by tainted value, policies), taint.py (poison/haircut/FIFO), peel.py
    risk/             exposure.py, rules.py (YAML rules → explained score)        [Phase 2]
    cases/            saved investigations: graph state, notes, annotations, watchlists
    jobs/             async background jobs with progress events (SSE), cancel, call budgets
    api/              FastAPI routers; cli.py (serve, import-tags, trace, screen)
  web/                React + TS + Vite, Cytoscape.js (+ELK layout), TanStack Query, Zustand, Tailwind
  data/               (gitignored) cache.db (disposable API cache), intel.db (labels, clusters, cases, user tags)
```

**Chain source.** `ChainSource` is an async Protocol with these methods:
- `get_tx`
- `get_outspends` (the Esplora `/tx/:id/outspends` endpoint, needed for forward tracing)
- `get_address_summary`
- `get_address_txs` (paginated)
- `get_tip_height`
- `get_price(ts)`

The `EsploraSource` backends are mempool.space (~1 req/s, honors `Retry-After`) and blockstream.info (optional API key; unauthenticated use is capped at 700 req/hour per IP and 500k req/month, so the default rate is 0.19 req/s). Any **self-hosted Esplora/mempool URL uses the same API**, so moving to your own node for tracing later needs no code change.

The backends are combined with per-backend token buckets, a failover rotation, and an optional `socks5h` Tor proxy. The Tor option is there for OPSEC, because public APIs see every address you query.

**Cache.** Txs with at least 6 confirmations are immutable and cached forever. Outspends, address pages and mempool data have short TTLs. Stored blobs are compressed JSON.

**Heuristics.** Each heuristic is a pure `async (tx, ctx) -> list[Finding]`, where `ctx` lazily fetches prevouts and outspends. Every finding carries a confidence and its evidence, and its ID links to the KB page. Change detection sums weighted log-odds votes across the H-CHG-* signals; an ML model can replace this later.

A test enforces that `catalog/heuristics.yaml` and the registry match.

**Clustering (local, Phase 1).**
- Union-find persisted in intel.db.
- CIOH is applied only on txs not flagged as CoinJoin or PayJoin.
- Change-based linking is opt-in and gated by a threshold.
- Cluster expansion is capped by addresses and API calls, and the result is marked `partial`.
- A cluster that exceeds the cap is flagged "large service (likely exchange)".
- Tags propagate address → cluster with provenance. Conflicting entity tags in one cluster raise a **cluster-collapse warning**.

**Tracing.** Forward or backward from an address, tx or outpoint, using a policy with these settings:
- max hops, max nodes, API-call budget, min value
- stop-at categories (e.g. exchange)
- CoinJoin: stop, or pass through with probabilistic links
- peel mode (auto-follow change)
- taint model

The engine expands the highest tainted value first ("follow the money") and streams graph increments to the UI.

**Risk screening (Phase 2).**
- Direct exposure (1 hop) and indirect exposure (N hops, haircut taint with hop decay), broken down by category.
- YAML rules turn the exposure into a score. Examples: any direct sanctioned exposure is severe; more than 10% indirect exposure to mixers is high.
- The output is an **explainable** report of paths, amounts, labels and sources.
- Batch screening via CSV.
- Behavioral flags: CoinJoin participant, peel-chain member, weak-key sweep, rapid dispersal.

**API.**
- `GET /api/tx/{txid}`
- `GET /api/address/{addr}`
- `GET /api/search?q=`
- `POST /api/trace` → job, and `GET /api/jobs/{id}/events` (SSE), plus cancel
- `POST /api/cluster/{addr}/expand`
- CRUD for `/api/cases` and `/api/tags`, and `POST /api/tags/import`
- `GET /api/kb/*`
- `POST /api/screen` (Phase 2)

Errors: invalid address or txid → 400 (the base58/bech32/bech32m checksum is validated locally). Source exhaustion returns partial results with `incomplete: true` and a reason. Every job has a call budget.

**Web workbench.**
- **Search:** address, txid or tag.
- **Graph canvas:** an address↔tx bipartite graph laid out left→right in time. Clusters are compound nodes that can be collapsed into one entity node. Nodes are colored by category and carry risk badges; edge width scales with BTC value, with an optional USD value at the time.
- **Context menu:** expand inputs or outputs, follow peel chain, trace N hops, expand cluster, tag, mark as change, hide.
- **Inspector:** tx fingerprint; heuristic findings with confidence, evidence and a link to the KB page; address and cluster details; tags with sources.
- **Case files:** saved layout, notes and a watchlist. Export to PNG/SVG, graph JSON, flow CSV and a Markdown/HTML report.
- **KB browser:** heuristics, techniques and incidents.
- **Screening page** (Phase 2).

---

## Phases (each gets its own spec → plan → implementation cycle)
- **Phase 0 — Knowledge base.** `docs/kb/` pages for every H-*, O-* and incident, plus `catalog/*.yaml`. Every factual claim and seed txid/address must cite a primary or peer-reviewed source, **verified at write time with no seeds from memory**. OAK IDs are fetched from onchainattack.org rather than guessed.
- **Phase 1 — Tracing workbench MVP.** Chain source and cache, heuristics (CIOH, change, fingerprint, CoinJoin detectors, motifs, THORChain memos), local clustering, label imports (TagPacks, OFAC, pools, ransomwhe.re), trace engine, API, and the web workbench with cases and export.
- **Phase 2 — Screening and monitoring.** Exposure and taint scoring, explainable rules, batch screening, watchlist polling with alerts (e.g. Bitget hacker addresses), Boltzmann/subset-sum CoinJoin link analysis, and an evaluation harness measuring precision against exchange proof-of-reserves sets and labeled entities.
- **Phase 3 — Own node and whole chain.** Needs ~2 TB SSD:
  - bitcoind plus self-hosted electrs/mempool as a drop-in Esplora source
  - bulk block ingest → Parquet/DuckDB
  - whole-chain CIOH clustering with a disk-backed union-find (int IDs via sorted Parquet, parents in a numpy memmap)
  - entity statistics and ML entity classification (Elliptic/Elliptic2 datasets)
- **Phase 4 — Cross-chain.** Follow THORChain, Chainflip and bridge exits onto ETH and Tron.

## Phase 0 + 1 build sequence (for the detailed implementation plan)
1. `git init`, Apache-2.0 LICENSE, README, `.gitignore`, install uv, backend skeleton (pyproject, ruff, pytest), `web/` Vite skeleton.
2. Phase 0 KB: taxonomy/categories, heuristics, techniques, incidents (sources verified via web), TTP matrix, references.
3. `chain/`: models, local validation, EsploraSource with rate limiting, retries and failover, SQLite cache, Tor proxy option. Fixtures are recorded real tx JSON.
4. `heuristics/`: fingerprint → CIOH → CoinJoin detectors (Wasabi1/2, Whirlpool, JoinMarket, Stonewall, generic) → change votes → motifs/peel → THORChain memo and cross-chain vault tags. Each is tested on recorded real txs whose ground truth comes from the coinjoin-analysis/Dumplings datasets and court filings.
5. `labels/`: store, taxonomy, and importers for TagPacks, OFAC, pools and ransomwhe.re; TagPack export of user tags.
6. `cluster/`: union-find, capped expansion, conflict detection.
7. `trace/`: taint models (property-tested for value conservation), engine with policies, budgets and a peel follower.
8. `jobs/` + `api/` + `cli.py`.
9. `web/`: search → graph canvas → inspector → context-menu expansion over SSE → clusters/tags → cases → export → KB browser.
10. End-to-end dogfood: trace a published incident seed (e.g. a court-documented ransom or hack tx) and reproduce the published hop path.

## Verification
- `uv run pytest`:
  - heuristics on recorded mainnet txs with known labels (CoinJoin types, coinbase, peel chains, THORChain memo txs)
  - `respx` recorded HTTP for source, cache and failover tests, including 429 and `Retry-After`
  - Hypothesis property tests: taint conservation, union-find invariants, FIFO range mapping
  - catalog↔registry↔KB consistency test
- `npm test` (vitest graph-state reducers) and a Playwright smoke test: search a txid → graph renders → expand outputs → inspector shows findings → save case → reload.
- **Manual end-to-end.** `btcintel serve` plus the web dev server. Trace a documented incident seed from `catalog/incidents/` and check that the hops, amounts and exit labels (exchange, mixer, THORChain memo) match the published analysis. Then screen a known OFAC-listed address and a known exchange PoR address.

## Process after this spec
1. Write this design as the spec at `docs/superpowers/specs/2026-09-25-btc-intel-design.md` (after `git init`) and commit it.
2. Owner reviews this spec.
3. Invoke **writing-plans** to produce the detailed task-level implementation plan for Phase 0 + Phase 1.
4. Owner chooses the execution method.
