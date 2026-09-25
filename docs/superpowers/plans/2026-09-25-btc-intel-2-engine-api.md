# btc-intel Plan 2 — Analysis Engine + API (Phase 1 backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Python analysis engine and local HTTP API:
- rate-limited, cached Esplora chain access with failover
- attribution labels (GraphSense TagPacks, OFAC, mining pools, ransomwhe.re)
- per-transaction heuristics (fingerprint, CoinJoin, CIOH, change, peel/fan motifs, THORChain memos, miner tags)
- local address clustering
- taint models and a streaming trace engine
- saved cases, background jobs, a FastAPI server and CLI commands

**Architecture:**
- `btcintel.chain` hides the data source behind the `ChainSource` protocol. `ChainClient` implements it over Esplora backends with a SQLite cache. A self-hosted Esplora or mempool instance is a drop-in replacement.
- `btcintel.heuristics` holds pure detectors that register under catalog IDs (`H-*`).
- `btcintel.labels` and `btcintel.cluster` persist in one SQLite database (`intel.db`).
- `btcintel.trace` expands a bipartite address↔tx graph by highest tainted value and emits incremental events.
- `btcintel.runtime.open_runtime` wires everything for the CLI and FastAPI (`btcintel.api`).

**Tech Stack:** Python 3.13, uv, pydantic v2, httpx (async, SOCKS support), FastAPI + uvicorn, sqlite3, PyYAML; tests with pytest, pytest-asyncio, respx, hypothesis.

**Spec:** `docs/superpowers/specs/2026-09-25-btc-intel-design.md`. **Requires Plan 1 to be complete**: the catalog, the `btcintel.chain.validate` module, and the pytest config with `pythonpath=["."]` and `--import-mode=importlib`.

## Global Constraints

- All Python commands run from `/home/fancybear/btc-intel/backend` via `uv run …`. Dependencies are added with `uv add`.
- Bitcoin mainnet only. Addresses are validated locally (`btcintel.chain.validate`) before any network call, and bech32 addresses are stored lowercase (`normalize_address`).
- **Heuristic IDs are the catalog contract.** Every registered detector ID must exist in `catalog/heuristics.yaml` with `status: implemented` and a resolvable `implemented_by`. When a task implements a heuristic, flip its catalog entry, update the KB page's "Detection in btc-intel" section, and re-render (`uv run btcintel catalog render`).
- Default backends: `mempool=https://mempool.space/api@1+price,blockstream=https://blockstream.info/api@4` (the value is `name=url@requests_per_second[+price]`). mempool.space undocumented limit is ≈1 req/s, so never raise it by default.
- Transactions with at least 6 confirmations are cached forever. Anything unconfirmed or shallower gets a short TTL (60 s for txs, 120 s for outspends and address data).
- Every network-triggering operation runs under a `CallBudget`. When a budget or backend fails, the operation returns a partial result flagged `incomplete: true` (trace) or `partial: true` (cluster) with a reason. It never hangs or crashes.
- The API binds to `127.0.0.1:8765` by default and has no authentication. `btcintel serve` warns when bound to a non-loopback host.
- Tests are offline by default. Live-network tests carry `@pytest.mark.network`.
- Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Public-API throttling in the middle of a large trace** (429s, 5xx, or a backend down). Expected: honour Retry-After, fail over to the next backend, and return `incomplete: true` with a reason. Tests: Task 5 `test_429_honours_retry_after`, Task 6 `test_failover_to_second_backend`, Task 15 `test_source_error_mid_trace_marks_incomplete`.
2. **A service address with a huge history (e.g. an exchange hot wallet) used as a trace or cluster seed.** Expected: bounded by `max_address_txs`, `max_txs_per_address`, `max_addresses` and the call budget, and marked partial/capped. Tests: Task 13 `test_expand_caps_cluster_size` and `test_expand_budget_marks_partial`; Task 15 `test_budget_exhaustion_marks_incomplete`.
3. **Unconfirmed (mempool) transactions and reorg-depth data.** These must never be cached permanently. Tests: Task 6 `test_unconfirmed_tx_uses_short_ttl` and `test_outspends_with_unspent_output_use_short_ttl`.
4. **User-supplied identifiers in API paths:** uppercase bech32, garbage strings, or path traversal in the KB page endpoint. Expected: normalised or rejected with 400, never a 500 or a file read outside `docs/kb`. Tests: Task 17 `test_uppercase_bech32_address_is_normalised`, `test_invalid_ids_return_400`, `test_kb_page_rejects_traversal`.
5. **Ordinary transactions misclassified as CoinJoins,** which would suppress clustering and stop traces. Expected: no strong CoinJoin kind on ordinary mainnet transactions. Test: Task 18 `test_ordinary_transactions_are_not_strong_coinjoins`.

---

## File Structure

```
backend/btcintel/config.py                 Settings, BackendConfig, parse_backends(), load_settings()
backend/btcintel/db.py                     open_intel_db(), transaction(), SCHEMA (tags, coinbase rules, clusters, cases)
backend/btcintel/runtime.py                AppState, open_runtime() — wires chain, db, stores, catalog
backend/btcintel/chain/errors.py           ChainError, NotFound, SourceError
backend/btcintel/chain/budget.py           CallBudget, BudgetExceeded, budget_scope(), charge_budget()
backend/btcintel/chain/models.py           TxOut, TxIn, TxStatus, Tx, Outspend, AddressStats
backend/btcintel/chain/esplora_parse.py    parse_tx(), parse_outspends(), parse_address()
backend/btcintel/chain/ratelimit.py        TokenBucket
backend/btcintel/chain/cache.py            Cache (SQLite KV with TTL, zlib JSON)
backend/btcintel/chain/esplora.py          EsploraBackend (retries, 429, failover-ready)
backend/btcintel/chain/source.py           ChainSource protocol
backend/btcintel/chain/client.py           ChainClient (cache policy, failover, pagination, price)
backend/btcintel/labels/taxonomy.py        Taxonomy (GraphSense concept mapping, risk)
backend/btcintel/labels/store.py           Tag, CONFIDENCE_LEVELS, TagStore
backend/btcintel/labels/tagpack.py         parse_tagpack(), export_tagpack()
backend/btcintel/labels/ofac.py            parse_sdn_xml()
backend/btcintel/labels/pools.py           parse_pools()
backend/btcintel/labels/ransomwhere.py     parse_ransomwhere()
backend/btcintel/labels/importers.py       ImportReport, import_* functions, source URLs
backend/btcintel/labels/lookup.py          AddressInfo, LabelLookup (tags + cluster + risk + stop category)
backend/btcintel/heuristics/base.py        Finding, Context, heuristic(), registry(), analyze_tx()
backend/btcintel/heuristics/fingerprint.py Fingerprint, fingerprint(), H-FP
backend/btcintel/heuristics/coinjoin.py    CoinJoinMatch, classify_coinjoin(), H-CJ (+children)
backend/btcintel/heuristics/cioh.py        cioh_addresses(), H-CIOH
backend/btcintel/heuristics/change.py      Vote, ChangeResult, offline_votes(), detect_change(), H-CHG (+children)
backend/btcintel/heuristics/patterns.py    peel_shape(), fanout_shape(), fanin_shape(), H-PEEL, H-MOTIF-FANOUT, H-MOTIF-FANIN
backend/btcintel/heuristics/crosschain.py  op_return_payloads(), ThorMemo, parse_thorchain_memo(), H-XCHAIN
backend/btcintel/heuristics/coinbase.py    match_pool(), H-COINBASE
backend/btcintel/heuristics/flags.py       tx_flags() — compact offline labels for graph nodes
backend/btcintel/heuristics/all.py         imports every detector module (registration)
backend/btcintel/cluster/unionfind.py      ClusterMeta, UnionFind (SQLite-persisted, union by size)
backend/btcintel/cluster/expand.py         ExpandPolicy, ExpandResult, Conflict, expand_cluster(), cluster_tags(), cluster_conflicts()
backend/btcintel/trace/taint.py            poison/haircut/fifo forward+backward, forward(), backward(), TAINT_MODELS
backend/btcintel/trace/graph.py            GraphNode, GraphEdge, Stop, GraphBuilder
backend/btcintel/trace/engine.py           TracePolicy, TraceSeed, TraceResult, trace()
backend/btcintel/trace/peel.py             PeelStep, PeelChain, follow_peel_chain()
backend/btcintel/cases/store.py            Case, CaseStore
backend/btcintel/jobs/manager.py           Job, JobManager
backend/btcintel/api/app.py                create_app()
backend/btcintel/api/deps.py               rt(), valid_txid(), valid_address()
backend/btcintel/api/routes_chain.py       /api/health, /api/search, /api/tx/*, /api/address/*
backend/btcintel/api/routes_trace.py       /api/trace, /api/peel, /api/jobs/*
backend/btcintel/api/routes_cluster.py     /api/cluster/*
backend/btcintel/api/routes_tags.py        /api/tags*
backend/btcintel/api/routes_cases.py       /api/cases*
backend/btcintel/api/routes_kb.py          /api/kb/*, /api/kb-page
backend/btcintel/cli.py                    + serve, import-tags, tags, tx, trace, cluster
backend/scripts/record_fixtures.py         records real-mainnet regression fixtures from ground-truth datasets
backend/tests/builders.py                  mk_tx(), op_return_script() — synthetic transactions
backend/tests/fakes.py                     FakeTime, FakeChain
backend/tests/fixtures/esplora/*.json      recorded Esplora responses
backend/tests/fixtures/real/**             recorded ground-truth CoinJoin / ordinary transactions
```

---

### Task 1: Runtime dependencies, settings, chain errors and call budgets

**Files:**
- Create: `backend/btcintel/config.py`, `backend/btcintel/chain/errors.py`, `backend/btcintel/chain/budget.py`
- Test: `backend/tests/test_config.py`, `backend/tests/chain/test_budget.py`

**Interfaces:**
- Consumes: `btcintel.paths.REPO_ROOT` (Plan 1).
- Produces:
  - `BackendConfig(name: str, base_url: str, rate_per_sec: float, burst: int = 1, supports_price: bool = False, headers: Mapping[str,str] = {})` (frozen dataclass)
  - `Settings(data_dir, catalog_dir, kb_dir, backends: tuple[BackendConfig, ...], proxy: str | None, host: str, port: int)`, with properties `cache_path` and `intel_path`
  - `DEFAULT_BACKENDS: str`, `parse_backends(spec: str) -> tuple[BackendConfig, ...]`, `load_settings(env: Mapping[str,str] | None = None) -> Settings`
  - `ChainError(Exception)`, `NotFound(ChainError)`, `SourceError(ChainError)`
  - `CallBudget(max_calls: int)` with `.used`, `.charge()`; `BudgetExceeded(ChainError)`; `budget_scope(budget)` context manager; `charge_budget() -> None` (charges the innermost active budget, no-op when none)

- [ ] **Step 1: Add dependencies**

```bash
cd /home/fancybear/btc-intel/backend
uv add "httpx[socks]>=0.27" "fastapi>=0.115" "uvicorn[standard]>=0.30"
uv add --dev "respx>=0.21"
```

- [ ] **Step 2: Write failing tests**

`backend/tests/test_config.py`:
```python
import pytest

from btcintel.config import DEFAULT_BACKENDS, load_settings, parse_backends


def test_default_backends():
    mempool, blockstream = parse_backends(DEFAULT_BACKENDS)
    assert (mempool.name, mempool.base_url, mempool.rate_per_sec, mempool.burst) == (
        "mempool", "https://mempool.space/api", 1.0, 1,
    )
    assert mempool.supports_price
    assert (blockstream.name, blockstream.rate_per_sec, blockstream.burst) == ("blockstream", 4.0, 4)
    assert not blockstream.supports_price


def test_self_hosted_backend_with_price_and_trailing_slash():
    (local,) = parse_backends("local=http://10.0.0.5:3006/api/@25+price")
    assert local.base_url == "http://10.0.0.5:3006/api"
    assert local.rate_per_sec == 25.0 and local.burst == 25 and local.supports_price


@pytest.mark.parametrize("spec", ["", "nourl", "x=http://a@0", "x=http://a", "x=http://a@abc"])
def test_invalid_backend_specs(spec):
    with pytest.raises(ValueError):
        parse_backends(spec)


def test_load_settings_from_env(tmp_path):
    s = load_settings({
        "BTCINTEL_DATA_DIR": str(tmp_path),
        "BTCINTEL_PROXY": "socks5h://127.0.0.1:9050",
        "BTCINTEL_PORT": "9999",
    })
    assert s.data_dir == tmp_path
    assert s.cache_path == tmp_path / "cache.db" and s.intel_path == tmp_path / "intel.db"
    assert s.proxy == "socks5h://127.0.0.1:9050"
    assert (s.host, s.port) == ("127.0.0.1", 9999)
    assert s.backends[0].name == "mempool"


def test_load_settings_defaults_point_into_repo():
    s = load_settings({})
    assert s.catalog_dir.name == "catalog" and s.kb_dir.parts[-2:] == ("docs", "kb")
    assert s.proxy is None
```

`backend/tests/chain/test_budget.py`:
```python
import pytest

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope, charge_budget
from btcintel.chain.errors import ChainError


def test_charge_without_scope_is_noop():
    charge_budget()


def test_scope_charges_until_exhausted():
    with budget_scope(CallBudget(2)) as b:
        charge_budget()
        charge_budget()
        with pytest.raises(BudgetExceeded):
            charge_budget()
    assert b.used == 2


def test_only_innermost_scope_is_charged():
    with budget_scope(CallBudget(5)) as outer:
        with budget_scope(CallBudget(1)) as inner:
            charge_budget()
        charge_budget()
    assert inner.used == 1 and outer.used == 1


def test_budget_exceeded_is_a_chain_error():
    assert issubclass(BudgetExceeded, ChainError)
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/test_config.py tests/chain/test_budget.py -v`
Expected: FAIL (modules missing).

- [ ] **Step 3: Implement**

`backend/btcintel/chain/errors.py`:
```python
"""Errors raised by chain data access."""


class ChainError(Exception):
    """Base class for chain data access errors."""


class NotFound(ChainError):
    """The requested transaction/address does not exist (HTTP 404/400 from the backend)."""


class SourceError(ChainError):
    """A backend failed (network, 5xx, repeated 429, unexpected status) or all backends failed."""
```

`backend/btcintel/chain/budget.py`:
```python
"""Per-operation limits on network calls (so traces/cluster expansions cannot run away)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from btcintel.chain.errors import ChainError


class BudgetExceeded(ChainError):
    """The active CallBudget has no calls left."""


@dataclass
class CallBudget:
    max_calls: int
    used: int = 0

    def charge(self) -> None:
        if self.used >= self.max_calls:
            raise BudgetExceeded(f"API call budget of {self.max_calls} exhausted")
        self.used += 1


_current: ContextVar[CallBudget | None] = ContextVar("btcintel_call_budget", default=None)


@contextmanager
def budget_scope(budget: CallBudget) -> Iterator[CallBudget]:
    token = _current.set(budget)
    try:
        yield budget
    finally:
        _current.reset(token)


def charge_budget() -> None:
    budget = _current.get()
    if budget is not None:
        budget.charge()
```

`backend/btcintel/config.py`:
```python
"""Runtime settings, read from BTCINTEL_* environment variables."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from btcintel.paths import REPO_ROOT

DEFAULT_BACKENDS = "mempool=https://mempool.space/api@1+price,blockstream=https://blockstream.info/api@4"


@dataclass(frozen=True)
class BackendConfig:
    name: str
    base_url: str
    rate_per_sec: float
    burst: int = 1
    supports_price: bool = False
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    catalog_dir: Path
    kb_dir: Path
    backends: tuple[BackendConfig, ...]
    proxy: str | None = None
    host: str = "127.0.0.1"
    port: int = 8765

    @property
    def cache_path(self) -> Path:
        return self.data_dir / "cache.db"

    @property
    def intel_path(self) -> Path:
        return self.data_dir / "intel.db"


def parse_backends(spec: str) -> tuple[BackendConfig, ...]:
    """Parse 'name=url@rate[+price],...' (rate = requests/second)."""
    backends = []
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        name, sep, rest = part.partition("=")
        url, at, rate_s = rest.rpartition("@")
        if not sep or not at or not name or not url:
            raise ValueError(f"backend {part!r}: expected name=url@rate[+price]")
        supports_price = rate_s.endswith("+price")
        try:
            rate = float(rate_s.removesuffix("+price"))
        except ValueError as e:
            raise ValueError(f"backend {part!r}: rate must be a number") from e
        if rate <= 0:
            raise ValueError(f"backend {part!r}: rate must be positive")
        backends.append(
            BackendConfig(
                name=name.strip(), base_url=url.strip().rstrip("/"), rate_per_sec=rate,
                burst=max(1, math.floor(rate)), supports_price=supports_price,
            )
        )
    if not backends:
        raise ValueError("no chain backends configured")
    return tuple(backends)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    return Settings(
        data_dir=Path(env.get("BTCINTEL_DATA_DIR", str(REPO_ROOT / "data"))),
        catalog_dir=Path(env.get("BTCINTEL_CATALOG_DIR", str(REPO_ROOT / "catalog"))),
        kb_dir=Path(env.get("BTCINTEL_KB_DIR", str(REPO_ROOT / "docs" / "kb"))),
        backends=parse_backends(env.get("BTCINTEL_BACKENDS", DEFAULT_BACKENDS)),
        proxy=env.get("BTCINTEL_PROXY") or None,
        host=env.get("BTCINTEL_HOST", "127.0.0.1"),
        port=int(env.get("BTCINTEL_PORT", "8765")),
    )
```

- [ ] **Step 4: Run tests**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/test_config.py tests/chain/test_budget.py -v && uv run ruff check .`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /home/fancybear/btc-intel
git add backend/pyproject.toml backend/uv.lock backend/btcintel/config.py backend/btcintel/chain/errors.py backend/btcintel/chain/budget.py backend/tests/test_config.py backend/tests/chain/test_budget.py
git commit -m "feat(chain): settings, chain errors and per-operation call budgets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Chain data models, Esplora parsing, and test builders

**Files:**
- Create: `backend/btcintel/chain/models.py`, `backend/btcintel/chain/esplora_parse.py`, `backend/tests/builders.py`
- Create (recorded): `backend/tests/fixtures/esplora/tx_c5908e04.json`, `tx_coinbase_900000.json`, `outspends_c5908e04.json`, `address_genesis.json`
- Test: `backend/tests/chain/test_models.py`

**Interfaces:**
- Consumes: nothing new.
- Produces (used by every later task; all frozen pydantic models):
  - `TxOut(n, value, script_type, address=None, script_hex="")`
  - `TxIn(n, prev_txid, prev_vout, prevout: TxOut | None, is_coinbase, sequence, scriptsig_hex, scriptsig_asm, witness: list[str], inner_redeemscript_asm, inner_witnessscript_asm)`, with properties `.value`, `.address` and `.script_type` taken from the prevout
  - `TxStatus(confirmed, block_height, block_hash, block_time)`
  - `Tx(txid, version, locktime, vin, vout, size, weight, fee, status)`, with computed fields `is_coinbase`, `input_value`, `output_value`, `vsize` and `feerate`, and methods `spendable_outputs()`, `input_addresses()` and `output_addresses()` (distinct, in order)
  - `Outspend(spent, txid=None, vin=None, status=None)`
  - `AddressStats(address, tx_count, funded_txo_count, funded_sum, spent_txo_count, spent_sum, mempool_tx_count=0, mempool_delta=0)`, with computed `balance`
  - `parse_tx(dict) -> Tx`, `parse_outspends(list) -> list[Outspend]`, `parse_address(dict) -> AddressStats`
  - `tests.builders.mk_tx(inputs, outputs, *, txid=None, version=2, locktime=0, sequence=0xFFFFFFFD, height=800_000, confirmed=True, coinbase=False, witness=None, scriptsig_hex="", op_returns=(), fee=None) -> Tx`
    - An input spec is `(address, value[, script_type])` or `(parent_tx, vout)`.
    - An output spec is `(address, value[, script_type])`.
    - `op_returns` is a list of payload `bytes`.
  - `tests.builders.op_return_script(payload: bytes) -> str`

- [ ] **Step 1: Record Esplora fixtures (real mainnet data)**

```bash
cd /home/fancybear/btc-intel/backend
mkdir -p tests/fixtures/esplora
curl -sf https://mempool.space/api/tx/c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c > tests/fixtures/esplora/tx_c5908e04.json
curl -sf https://mempool.space/api/tx/21a71ec52cee51aa32db9cb7c1d2a3f016ce9a182403a7d1892761c397c87c4c > tests/fixtures/esplora/tx_coinbase_900000.json
curl -sf https://mempool.space/api/tx/c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c/outspends > tests/fixtures/esplora/outspends_c5908e04.json
curl -sf https://mempool.space/api/address/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa > tests/fixtures/esplora/address_genesis.json
python3 -m json.tool tests/fixtures/esplora/tx_c5908e04.json | head -5
```
Expected: valid JSON starting with `"txid": "c5908e04…"`. These are the second and first (coinbase) transactions of block 900000.

- [ ] **Step 2: Write the failing tests**

`backend/tests/chain/test_models.py`:
```python
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
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_models.py -v`
Expected: FAIL (modules missing).

- [ ] **Step 3: Implement models and parser**

`backend/btcintel/chain/models.py`:
```python
"""Source-agnostic chain data models (shaped after the Esplora REST API)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, computed_field


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class TxOut(_Frozen):
    n: int
    value: int
    script_type: str
    address: str | None = None
    script_hex: str = ""


class TxIn(_Frozen):
    n: int
    prev_txid: str
    prev_vout: int
    prevout: TxOut | None = None
    is_coinbase: bool = False
    sequence: int
    scriptsig_hex: str = ""
    scriptsig_asm: str = ""
    witness: list[str] = []
    inner_redeemscript_asm: str | None = None
    inner_witnessscript_asm: str | None = None

    @property
    def value(self) -> int:
        return self.prevout.value if self.prevout else 0

    @property
    def address(self) -> str | None:
        return self.prevout.address if self.prevout else None

    @property
    def script_type(self) -> str | None:
        return self.prevout.script_type if self.prevout else None


class TxStatus(_Frozen):
    confirmed: bool
    block_height: int | None = None
    block_hash: str | None = None
    block_time: int | None = None


class Tx(_Frozen):
    txid: str
    version: int
    locktime: int
    vin: list[TxIn]
    vout: list[TxOut]
    size: int
    weight: int
    fee: int
    status: TxStatus

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_coinbase(self) -> bool:
        return bool(self.vin) and self.vin[0].is_coinbase

    @computed_field  # type: ignore[prop-decorator]
    @property
    def input_value(self) -> int:
        return sum(i.value for i in self.vin)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def output_value(self) -> int:
        return sum(o.value for o in self.vout)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def vsize(self) -> int:
        return (self.weight + 3) // 4

    @computed_field  # type: ignore[prop-decorator]
    @property
    def feerate(self) -> float:
        return round(self.fee / self.vsize, 3) if self.vsize else 0.0

    def spendable_outputs(self) -> list[TxOut]:
        return [o for o in self.vout if o.script_type != "op_return"]

    def input_addresses(self) -> list[str]:
        return list(dict.fromkeys(i.address for i in self.vin if i.address))

    def output_addresses(self) -> list[str]:
        return list(dict.fromkeys(o.address for o in self.vout if o.address))


class Outspend(_Frozen):
    spent: bool
    txid: str | None = None
    vin: int | None = None
    status: TxStatus | None = None


class AddressStats(_Frozen):
    address: str
    tx_count: int
    funded_txo_count: int
    funded_sum: int
    spent_txo_count: int
    spent_sum: int
    mempool_tx_count: int = 0
    mempool_delta: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def balance(self) -> int:
        return self.funded_sum - self.spent_sum
```

`backend/btcintel/chain/esplora_parse.py`:
```python
"""Convert Esplora (mempool.space / blockstream.info / electrs) JSON into chain models."""

from __future__ import annotations

from typing import Any

from btcintel.chain.models import AddressStats, Outspend, Tx, TxIn, TxOut, TxStatus


def _out(j: dict[str, Any], n: int) -> TxOut:
    return TxOut(
        n=n,
        value=j["value"],
        script_type=j.get("scriptpubkey_type", "unknown"),
        address=j.get("scriptpubkey_address"),
        script_hex=j.get("scriptpubkey", ""),
    )


def _status(j: dict[str, Any] | None) -> TxStatus:
    j = j or {}
    return TxStatus(
        confirmed=bool(j.get("confirmed")),
        block_height=j.get("block_height"),
        block_hash=j.get("block_hash"),
        block_time=j.get("block_time"),
    )


def parse_tx(j: dict[str, Any]) -> Tx:
    vin = []
    for i, v in enumerate(j["vin"]):
        prev = v.get("prevout")
        vin.append(
            TxIn(
                n=i,
                prev_txid=v["txid"],
                prev_vout=v["vout"],
                prevout=_out(prev, v["vout"]) if prev else None,
                is_coinbase=bool(v.get("is_coinbase", False)),
                sequence=v["sequence"],
                scriptsig_hex=v.get("scriptsig", "") or "",
                scriptsig_asm=v.get("scriptsig_asm", "") or "",
                witness=v.get("witness") or [],
                inner_redeemscript_asm=v.get("inner_redeemscript_asm"),
                inner_witnessscript_asm=v.get("inner_witnessscript_asm"),
            )
        )
    return Tx(
        txid=j["txid"],
        version=j["version"],
        locktime=j["locktime"],
        vin=vin,
        vout=[_out(o, n) for n, o in enumerate(j["vout"])],
        size=j["size"],
        weight=j["weight"],
        fee=j.get("fee", 0),
        status=_status(j.get("status")),
    )


def parse_outspends(j: list[dict[str, Any]]) -> list[Outspend]:
    return [
        Outspend(
            spent=bool(o.get("spent", False)),
            txid=o.get("txid"),
            vin=o.get("vin"),
            status=_status(o["status"]) if o.get("status") else None,
        )
        for o in j
    ]


def parse_address(j: dict[str, Any]) -> AddressStats:
    chain = j["chain_stats"]
    mem = j.get("mempool_stats") or {}
    return AddressStats(
        address=j["address"],
        tx_count=chain["tx_count"],
        funded_txo_count=chain["funded_txo_count"],
        funded_sum=chain["funded_txo_sum"],
        spent_txo_count=chain["spent_txo_count"],
        spent_sum=chain["spent_txo_sum"],
        mempool_tx_count=mem.get("tx_count", 0),
        mempool_delta=mem.get("funded_txo_sum", 0) - mem.get("spent_txo_sum", 0),
    )
```

`backend/tests/builders.py`:
```python
"""Synthetic transaction builders for unit tests (no network)."""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Sequence
from typing import Any

from btcintel.chain.models import Tx, TxIn, TxOut, TxStatus

_seq = itertools.count()


def fake_txid(tag: str | None = None) -> str:
    return hashlib.sha256((tag or f"tx-{next(_seq)}").encode()).hexdigest()


def op_return_script(payload: bytes) -> str:
    if len(payload) <= 75:
        return "6a" + f"{len(payload):02x}" + payload.hex()
    return "6a4c" + f"{len(payload):02x}" + payload.hex()


def mk_tx(
    inputs: Sequence[tuple[Any, ...]],
    outputs: Sequence[tuple[Any, ...]],
    *,
    txid: str | None = None,
    version: int = 2,
    locktime: int = 0,
    sequence: int = 0xFFFFFFFD,
    height: int | None = 800_000,
    confirmed: bool = True,
    coinbase: bool = False,
    witness: Sequence[Sequence[str]] | None = None,
    scriptsig_hex: str = "",
    op_returns: Sequence[bytes] = (),
    fee: int | None = None,
) -> Tx:
    """inputs: (address, value[, script_type]) or (parent_tx, vout); outputs: (address, value[, script_type])."""
    vin: list[TxIn] = []
    for i, spec in enumerate(inputs):
        if isinstance(spec[0], Tx):
            parent, vout = spec[0], spec[1]
            prev_txid, prev_vout, prevout = parent.txid, vout, parent.vout[vout]
        else:
            addr, value, *rest = spec
            st = rest[0] if rest else "v0_p2wpkh"
            prev_txid, prev_vout = fake_txid(), 0
            prevout = TxOut(n=0, value=value, address=addr, script_type=st)
        vin.append(
            TxIn(
                n=i,
                prev_txid="0" * 64 if coinbase else prev_txid,
                prev_vout=0xFFFFFFFF if coinbase else prev_vout,
                prevout=None if coinbase else prevout,
                is_coinbase=coinbase,
                sequence=sequence,
                scriptsig_hex=scriptsig_hex,
                witness=list(witness[i]) if witness else [],
            )
        )
    vout = [
        TxOut(n=n, value=value, address=addr, script_type=rest[0] if rest else "v0_p2wpkh")
        for n, (addr, value, *rest) in enumerate(outputs)
    ]
    for payload in op_returns:
        vout.append(TxOut(n=len(vout), value=0, script_type="op_return", script_hex=op_return_script(payload)))
    in_value = sum(i.value for i in vin)
    out_value = sum(o.value for o in vout)
    return Tx(
        txid=txid or fake_txid(),
        version=version,
        locktime=locktime,
        vin=vin,
        vout=vout,
        size=250,
        weight=1000,
        fee=fee if fee is not None else max(0, in_value - out_value),
        status=TxStatus(
            confirmed=confirmed,
            block_height=height if confirmed else None,
            block_time=1_700_000_000 if confirmed else None,
        ),
    )
```

- [ ] **Step 4: Run tests**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_models.py -v && uv run ruff check .`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/chain/models.py backend/btcintel/chain/esplora_parse.py backend/tests/builders.py backend/tests/fixtures/esplora backend/tests/chain/test_models.py
git commit -m "feat(chain): Esplora-shaped chain models, parser, recorded fixtures, test builders

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Token-bucket rate limiter

**Files:**
- Create: `backend/btcintel/chain/ratelimit.py`, `backend/tests/fakes.py`
- Test: `backend/tests/chain/test_ratelimit.py`

**Interfaces:**
- Produces:
  - `TokenBucket(rate: float, burst: int = 1, clock=time.monotonic, sleep=asyncio.sleep)` with `async acquire()`, `penalize(seconds: float)` (block until now+seconds, used for HTTP 429 Retry-After) and `next_available() -> float` (seconds until a request may proceed)
  - `tests.fakes.FakeTime`, with `.now`, `.sleeps`, `.clock()` and `async .sleep(s)` that advances `now`

- [ ] **Step 1: Write the failing tests**

`backend/tests/fakes.py` (initial content; Task 6 appends `FakeChain`):
```python
"""Test doubles shared across the test suite."""

from __future__ import annotations


class FakeTime:
    """Deterministic clock + sleep: sleeping advances the clock instantly."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(round(seconds, 6))
        self.now += seconds
```

`backend/tests/chain/test_ratelimit.py`:
```python
import pytest

from btcintel.chain.ratelimit import TokenBucket
from tests.fakes import FakeTime


async def test_burst_then_rate_limited():
    ft = FakeTime()
    bucket = TokenBucket(rate=1.0, burst=2, clock=ft.clock, sleep=ft.sleep)
    for _ in range(3):
        await bucket.acquire()
    assert ft.sleeps == [1.0]


async def test_penalize_blocks_until_deadline():
    ft = FakeTime()
    bucket = TokenBucket(rate=10.0, burst=1, clock=ft.clock, sleep=ft.sleep)
    await bucket.acquire()
    bucket.penalize(5.0)
    await bucket.acquire()
    assert ft.now == pytest.approx(5.0)


async def test_next_available_reports_wait():
    ft = FakeTime()
    bucket = TokenBucket(rate=2.0, burst=1, clock=ft.clock, sleep=ft.sleep)
    assert bucket.next_available() == 0.0
    await bucket.acquire()
    assert bucket.next_available() == pytest.approx(0.5)
    bucket.penalize(3.0)
    assert bucket.next_available() == pytest.approx(3.0)


@pytest.mark.parametrize("rate,burst", [(0, 1), (-1, 1), (1, 0)])
def test_invalid_parameters(rate, burst):
    with pytest.raises(ValueError):
        TokenBucket(rate=rate, burst=burst)
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_ratelimit.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/chain/ratelimit.py`:
```python
"""Async token bucket used to respect public API rate limits."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class TokenBucket:
    def __init__(
        self,
        rate: float,
        burst: int = 1,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate <= 0 or burst < 1:
            raise ValueError("rate must be > 0 and burst >= 1")
        self.rate = rate
        self.burst = burst
        self._clock = clock
        self._sleep = sleep
        self._tokens = float(burst)
        self._last = clock()
        self._blocked_until = 0.0
        self._lock = asyncio.Lock()

    def _refill(self, now: float) -> None:
        self._tokens = min(float(self.burst), self._tokens + (now - self._last) * self.rate)
        self._last = now

    def next_available(self) -> float:
        now = self._clock()
        self._refill(now)
        token_wait = 0.0 if self._tokens >= 1 else (1 - self._tokens) / self.rate
        return max(token_wait, self._blocked_until - now, 0.0)

    def penalize(self, seconds: float) -> None:
        self._blocked_until = max(self._blocked_until, self._clock() + seconds)

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._clock()
                self._refill(now)
                if now < self._blocked_until:
                    await self._sleep(self._blocked_until - now)
                    continue
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await self._sleep((1 - self._tokens) / self.rate)
```

- [ ] **Step 3: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_ratelimit.py -v`
Expected: 6 passed.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/chain/ratelimit.py backend/tests/fakes.py backend/tests/chain/test_ratelimit.py
git commit -m "feat(chain): async token-bucket rate limiter with 429 penalty

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: SQLite response cache

**Files:**
- Create: `backend/btcintel/chain/cache.py`
- Test: `backend/tests/chain/test_cache.py`

**Interfaces:**
- Produces: `Cache(path: Path | str, clock: Callable[[], float] = time.time)` with `get_json(key) -> Any | None`, `put_json(key, obj, ttl: float | None)` (`None` = never expires), `purge_expired() -> int` and `close()`. `":memory:"` is supported.

- [ ] **Step 1: Write the failing tests**

`backend/tests/chain/test_cache.py`:
```python
from btcintel.chain.cache import Cache


def test_roundtrip_and_missing(tmp_path):
    c = Cache(tmp_path / "c.db")
    c.put_json("k", {"a": [1, 2]}, ttl=None)
    assert c.get_json("k") == {"a": [1, 2]}
    assert c.get_json("missing") is None


def test_ttl_expiry_and_purge(tmp_path):
    now = [1000.0]
    c = Cache(tmp_path / "c.db", clock=lambda: now[0])
    c.put_json("k", 1, ttl=10)
    c.put_json("forever", 2, ttl=None)
    now[0] = 1009.9
    assert c.get_json("k") == 1
    now[0] = 1010.0
    assert c.get_json("k") is None
    assert c.get_json("forever") == 2
    assert c.purge_expired() == 1


def test_overwrite_replaces_value_and_ttl(tmp_path):
    now = [0.0]
    c = Cache(tmp_path / "c.db", clock=lambda: now[0])
    c.put_json("k", "old", ttl=1)
    c.put_json("k", "new", ttl=None)
    now[0] = 100
    assert c.get_json("k") == "new"


def test_persists_across_instances(tmp_path):
    Cache(tmp_path / "c.db").put_json("k", [1], ttl=None)
    assert Cache(tmp_path / "c.db").get_json("k") == [1]


def test_memory_cache_and_nested_dir(tmp_path):
    Cache(":memory:").put_json("k", 1, ttl=None)
    c = Cache(tmp_path / "a" / "b" / "c.db")
    c.put_json("x", True, ttl=None)
    assert c.get_json("x") is True
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_cache.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/chain/cache.py`:
```python
"""Persistent key/value cache for API responses (zlib-compressed JSON in SQLite)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, path: Path | str, clock: Callable[[], float] = time.time) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value BLOB NOT NULL, expires REAL)"
        )
        self._lock = threading.Lock()
        self._clock = clock

    def get_json(self, key: str) -> Any | None:
        with self._lock:
            row = self._db.execute("SELECT value, expires FROM kv WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        value, expires = row
        if expires is not None and expires <= self._clock():
            return None
        return json.loads(zlib.decompress(value))

    def put_json(self, key: str, obj: Any, ttl: float | None) -> None:
        blob = zlib.compress(json.dumps(obj, separators=(",", ":")).encode(), 6)
        expires = None if ttl is None else self._clock() + ttl
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO kv (key, value, expires) VALUES (?, ?, ?)",
                (key, blob, expires),
            )

    def purge_expired(self) -> int:
        with self._lock:
            cur = self._db.execute(
                "DELETE FROM kv WHERE expires IS NOT NULL AND expires <= ?", (self._clock(),)
            )
        return cur.rowcount

    def close(self) -> None:
        self._db.close()
```

- [ ] **Step 3: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_cache.py -v`
Expected: 5 passed.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/chain/cache.py backend/tests/chain/test_cache.py
git commit -m "feat(chain): SQLite response cache with TTLs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Esplora HTTP backend (retries, 429, budget charging)

**Files:**
- Create: `backend/btcintel/chain/esplora.py`
- Test: `backend/tests/chain/test_esplora.py`

**Interfaces:**
- Consumes: `BackendConfig` (Task 1), `TokenBucket` (Task 3), `charge_budget`, `NotFound`, `SourceError`.
- Produces: `EsploraBackend(cfg, client: httpx.AsyncClient, *, bucket: TokenBucket | None = None, max_retries: int = 4, sleep=asyncio.sleep)`, with attributes `.name`, `.supports_price` and `.bucket`, and methods `async get_json(path) -> Any` and `async get_text(path) -> str`.

Behaviour:
- Each attempt calls `bucket.acquire()` and then `charge_budget()`.
- 200 → return the response.
- 400 or 404 → `NotFound`, with no retry.
- 429 → penalise the bucket by `Retry-After` seconds (default: exponential backoff) and retry.
- 5xx or transport error → sleep with backoff `min(30, 0.5·2^attempt)` and retry.
- Any other status → `SourceError`.
- Exhausting all `max_retries + 1` attempts → `SourceError("… failed after N attempts …")`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/chain/test_esplora.py`:
```python
import httpx
import pytest
import respx

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.ratelimit import TokenBucket
from btcintel.config import BackendConfig
from tests.fakes import FakeTime

BASE = "https://esplora.test/api"


@pytest.fixture
async def backend():
    ft = FakeTime()
    async with httpx.AsyncClient() as client:
        cfg = BackendConfig(name="t", base_url=BASE, rate_per_sec=100.0, burst=100,
                            headers={"Authorization": "Bearer tok"})
        bucket = TokenBucket(100.0, 100, clock=ft.clock, sleep=ft.sleep)
        yield EsploraBackend(cfg, client, bucket=bucket, sleep=ft.sleep), ft


@respx.mock(assert_all_called=False)
async def test_get_json_ok_and_headers_sent(backend):
    b, _ = backend
    route = respx.get(f"{BASE}/tx/abc").mock(return_value=httpx.Response(200, json={"txid": "abc"}))
    assert await b.get_json("/tx/abc") == {"txid": "abc"}
    assert route.call_count == 1
    assert route.calls[0].request.headers["Authorization"] == "Bearer tok"


@respx.mock(assert_all_called=False)
@pytest.mark.parametrize("status", [400, 404])
async def test_client_errors_are_not_found_without_retry(backend, status):
    b, _ = backend
    route = respx.get(f"{BASE}/tx/zz").mock(return_value=httpx.Response(status, text="nope"))
    with pytest.raises(NotFound):
        await b.get_json("/tx/zz")
    assert route.call_count == 1


@respx.mock(assert_all_called=False)
async def test_429_honours_retry_after(backend):
    b, ft = backend
    route = respx.get(f"{BASE}/x").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json=[1]),
    ])
    assert await b.get_json("/x") == [1]
    assert route.call_count == 2
    assert ft.now >= 7


@respx.mock(assert_all_called=False)
async def test_5xx_retried_with_backoff_then_source_error(backend):
    b, ft = backend
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(503))
    with pytest.raises(SourceError, match="failed after 5 attempts"):
        await b.get_json("/x")
    assert route.call_count == 5
    assert ft.sleeps == [0.5, 1.0, 2.0, 4.0, 8.0]


@respx.mock(assert_all_called=False)
async def test_transport_error_is_retried(backend):
    b, _ = backend
    respx.get(f"{BASE}/blocks/tip/height").mock(side_effect=[
        httpx.ConnectError("boom"),
        httpx.Response(200, text="900000"),
    ])
    assert await b.get_text("/blocks/tip/height") == "900000"


@respx.mock(assert_all_called=False)
async def test_each_attempt_charges_the_budget(backend):
    b, _ = backend
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(503))
    with budget_scope(CallBudget(2)), pytest.raises(BudgetExceeded):
        await b.get_json("/x")
    assert route.call_count == 2


@respx.mock(assert_all_called=False)
async def test_unexpected_status_is_source_error(backend):
    b, _ = backend
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(418))
    with pytest.raises(SourceError, match="HTTP 418"):
        await b.get_json("/x")
    assert route.call_count == 1
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_esplora.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/chain/esplora.py`:
```python
"""One Esplora-compatible HTTP backend (mempool.space, blockstream.info, self-hosted)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from btcintel.chain.budget import charge_budget
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.ratelimit import TokenBucket
from btcintel.config import BackendConfig


def _backoff(attempt: int) -> float:
    return min(30.0, 0.5 * 2**attempt)


def _retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None  # HTTP-date form: fall back to exponential backoff


class EsploraBackend:
    def __init__(
        self,
        cfg: BackendConfig,
        client: httpx.AsyncClient,
        *,
        bucket: TokenBucket | None = None,
        max_retries: int = 4,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.cfg = cfg
        self.name = cfg.name
        self.supports_price = cfg.supports_price
        self.client = client
        self.bucket = bucket or TokenBucket(cfg.rate_per_sec, cfg.burst)
        self.max_retries = max_retries
        self._sleep = sleep

    async def get_json(self, path: str) -> Any:
        return (await self._request(path)).json()

    async def get_text(self, path: str) -> str:
        return (await self._request(path)).text

    async def _request(self, path: str) -> httpx.Response:
        url = self.cfg.base_url + path
        last = "no attempt made"
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            await self.bucket.acquire()
            charge_budget()
            try:
                resp = await self.client.get(url, headers=dict(self.cfg.headers))
            except httpx.TransportError as e:
                last = f"{type(e).__name__}: {e}"
                await self._sleep(_backoff(attempt))
                continue
            status = resp.status_code
            if status == 200:
                return resp
            if status in (400, 404):
                raise NotFound(f"{self.name}: {path} (HTTP {status})")
            if status == 429:
                self.bucket.penalize(_retry_after(resp.headers.get("Retry-After")) or _backoff(attempt))
                last = "HTTP 429"
                continue
            if status >= 500:
                last = f"HTTP {status}"
                await self._sleep(_backoff(attempt))
                continue
            raise SourceError(f"{self.name}: {path} HTTP {status}")
        raise SourceError(f"{self.name}: {path} failed after {attempts} attempts ({last})")
```

- [ ] **Step 3: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_esplora.py -v`
Expected: 8 passed.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/chain/esplora.py backend/tests/chain/test_esplora.py
git commit -m "feat(chain): Esplora HTTP backend with retries, 429 handling and budget charging

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: ChainSource protocol, ChainClient (cache policy, failover, pagination, price) and FakeChain

**Files:**
- Create: `backend/btcintel/chain/source.py`, `backend/btcintel/chain/client.py`
- Modify: `backend/tests/fakes.py` (append `FakeChain`)
- Test: `backend/tests/chain/test_client.py`, `backend/tests/test_fakes.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces:
  - `ChainSource` (typing `Protocol`), with these async methods (`iter_address_txs` is an async generator):
    - `get_tx(txid) -> Tx`
    - `get_outspends(txid) -> list[Outspend]`
    - `get_address(address) -> AddressStats`
    - `get_address_txs(address, after_txid=None) -> list[Tx]`
    - `iter_address_txs(address, max_txs=1000) -> AsyncIterator[Tx]`
    - `tip_height() -> int`
    - `get_price_usd(ts: int) -> float | None`
  - `ChainClient(backends: Sequence[EsploraBackend], cache: Cache, *, tip_ttl=30.0)` implements `ChainSource` and exposes `.cache`.
  - Constants `IMMUTABLE_CONFIRMATIONS = 6`, `SHALLOW_TX_TTL = 60.0`, `VOLATILE_TTL = 120.0`.
  - `tests.fakes.FakeChain(txs=(), tip=900_000, fail_on: set[str] = ())`, an in-memory `ChainSource`:
    - derives outspends and per-address history from the transactions it holds
    - counts `.calls` and charges the active budget on each call
    - raises `SourceError` for txids in `fail_on`
    - `add(*txs)` adds transactions

- [ ] **Step 1: Write the failing tests**

`backend/tests/chain/test_client.py`:
```python
import copy
import json
from pathlib import Path

import httpx
import pytest
import respx

from btcintel.chain.cache import Cache
from btcintel.chain.client import ChainClient
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.ratelimit import TokenBucket
from btcintel.config import BackendConfig
from tests.fakes import FakeTime

A = "https://a.test/api"
B = "https://b.test/api"
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"
TXID = "c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c"


def fixture_tx(txid: str = TXID, confirmed: bool = True, height: int = 900000) -> dict:
    d = copy.deepcopy(json.loads((FIX / "tx_c5908e04.json").read_text()))
    d["txid"] = txid
    d["status"] = {"confirmed": confirmed, "block_height": height if confirmed else None,
                   "block_hash": "00" * 32 if confirmed else None,
                   "block_time": 1749188499 if confirmed else None}
    return d


@pytest.fixture
async def make_client(tmp_path):
    http = httpx.AsyncClient()
    now = [1_000_000.0]
    ft = FakeTime()

    def _make() -> ChainClient:
        def backend(name: str, base: str, price: bool) -> EsploraBackend:
            cfg = BackendConfig(name=name, base_url=base, rate_per_sec=100.0, burst=100, supports_price=price)
            return EsploraBackend(cfg, http, bucket=TokenBucket(100.0, 100, clock=ft.clock, sleep=ft.sleep),
                                  sleep=ft.sleep)
        cache = Cache(tmp_path / "cache.db", clock=lambda: now[0])
        return ChainClient([backend("a", A, True), backend("b", B, False)], cache)

    _make.now = now  # type: ignore[attr-defined]
    yield _make
    await http.aclose()


@respx.mock(assert_all_called=False)
async def test_deep_tx_is_cached_forever(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    route = respx.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    first = await client.get_tx(TXID)
    make_client.now[0] += 10 * 86400
    second = await client.get_tx(TXID)
    assert first == second and route.call_count == 1


@respx.mock(assert_all_called=False)
async def test_unconfirmed_tx_uses_short_ttl(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    route = respx.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx(confirmed=False)))
    await client.get_tx(TXID)
    await client.get_tx(TXID)
    assert route.call_count == 1
    make_client.now[0] += 61
    await client.get_tx(TXID)
    assert route.call_count == 2


@respx.mock(assert_all_called=False)
async def test_shallow_confirmed_tx_uses_short_ttl(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900002"))
    route = respx.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx(height=900000)))
    await client.get_tx(TXID)
    make_client.now[0] += 61
    await client.get_tx(TXID)
    assert route.call_count == 2


@respx.mock(assert_all_called=False)
async def test_failover_to_second_backend(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    respx.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(503))
    b_route = respx.get(f"{B}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    tx = await client.get_tx(TXID)
    assert tx.txid == TXID and b_route.call_count == 1


@respx.mock(assert_all_called=False)
async def test_not_found_does_not_fail_over(make_client):
    client = make_client()
    respx.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(404, text="Transaction not found"))
    b_route = respx.get(f"{B}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    with pytest.raises(NotFound):
        await client.get_tx(TXID)
    assert b_route.call_count == 0


@respx.mock(assert_all_called=False)
async def test_all_backends_failing_raises_source_error(make_client):
    client = make_client()
    respx.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(503))
    respx.get(f"{B}/tx/{TXID}").mock(return_value=httpx.Response(503))
    with pytest.raises(SourceError, match="all backends failed"):
        await client.get_tx(TXID)


@respx.mock(assert_all_called=False)
async def test_tip_height_is_cached(make_client):
    client = make_client()
    route = respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100\n"))
    assert await client.tip_height() == 900100
    assert await client.tip_height() == 900100
    assert route.call_count == 1


@respx.mock(assert_all_called=False)
async def test_outspends_all_spent_deep_cached_forever(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    body = [{"spent": True, "txid": "ab" * 32, "vin": 0,
             "status": {"confirmed": True, "block_height": 900001}}]
    route = respx.get(f"{A}/tx/{TXID}/outspends").mock(return_value=httpx.Response(200, json=body))
    await client.get_outspends(TXID)
    make_client.now[0] += 86400
    spends = await client.get_outspends(TXID)
    assert spends[0].spent and route.call_count == 1


@respx.mock(assert_all_called=False)
async def test_outspends_with_unspent_output_use_short_ttl(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    route = respx.get(f"{A}/tx/{TXID}/outspends").mock(return_value=httpx.Response(200, json=[{"spent": False}]))
    await client.get_outspends(TXID)
    make_client.now[0] += 121
    await client.get_outspends(TXID)
    assert route.call_count == 2


@respx.mock(assert_all_called=False)
async def test_address_history_pagination(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    ids = [f"{i:064x}" for i in range(1, 5)]
    addr = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
    p1 = respx.get(f"{A}/address/{addr}/txs").mock(
        return_value=httpx.Response(200, json=[fixture_tx(t) for t in ids[:3]]))
    respx.get(f"{A}/address/{addr}/txs/chain/{ids[2]}").mock(
        return_value=httpx.Response(200, json=[fixture_tx(ids[3])]))
    respx.get(f"{A}/address/{addr}/txs/chain/{ids[3]}").mock(return_value=httpx.Response(200, json=[]))
    got = [t.txid async for t in client.iter_address_txs(addr)]
    assert got == ids
    limited = [t.txid async for t in make_client().iter_address_txs(addr, max_txs=2)]
    assert limited == ids[:2] and p1.call_count >= 1


@respx.mock(assert_all_called=False)
async def test_address_txs_warm_the_tx_cache(make_client):
    client = make_client()
    respx.get(f"{A}/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    addr = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
    respx.get(f"{A}/address/{addr}/txs").mock(return_value=httpx.Response(200, json=[fixture_tx()]))
    tx_route = respx.get(f"{A}/tx/{TXID}").mock(return_value=httpx.Response(200, json=fixture_tx()))
    await client.get_address_txs(addr)
    await client.get_tx(TXID)
    assert tx_route.call_count == 0


@respx.mock(assert_all_called=False)
async def test_price_uses_price_backend_and_hour_bucket(make_client):
    client = make_client()
    route = respx.get(f"{A}/v1/historical-price", params={"currency": "USD", "timestamp": "1749186000"}).mock(
        return_value=httpx.Response(200, json={"prices": [{"time": 1749186000, "USD": 102863}]}))
    assert await client.get_price_usd(1749188499) == 102863.0
    assert await client.get_price_usd(1749188000) == 102863.0
    assert route.call_count == 1


@respx.mock(assert_all_called=False)
async def test_price_unavailable_returns_none(make_client):
    client = make_client()
    respx.get(f"{A}/v1/historical-price").mock(return_value=httpx.Response(404))
    assert await client.get_price_usd(1749188499) is None


@respx.mock(assert_all_called=False)
async def test_get_address(make_client):
    client = make_client()
    body = json.loads((FIX / "address_genesis.json").read_text())
    respx.get(f"{A}/address/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa").mock(return_value=httpx.Response(200, json=body))
    st = await client.get_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    assert st.address == "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
```

`backend/tests/test_fakes.py`:
```python
import pytest

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import NotFound, SourceError
from tests.builders import mk_tx
from tests.fakes import FakeChain

A1 = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
A2 = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"


async def test_fake_chain_derives_outspends_and_history():
    parent = mk_tx([(A1, 100_000, "p2pkh")], [(A2, 60_000), (A1, 39_000, "p2pkh")])
    child = mk_tx([(parent, 0)], [(A1, 59_000, "p2pkh")])
    chain = FakeChain([parent, child])
    spends = await chain.get_outspends(parent.txid)
    assert spends[0].spent and spends[0].txid == child.txid and spends[0].vin == 0
    assert not spends[1].spent
    assert [t.txid async for t in chain.iter_address_txs(A2)] == [parent.txid, child.txid]
    stats = await chain.get_address(A2)
    assert stats.funded_sum == 60_000 and stats.spent_sum == 60_000 and stats.tx_count == 2


async def test_fake_chain_errors_and_budget():
    tx = mk_tx([(A1, 1000, "p2pkh")], [(A2, 900)])
    chain = FakeChain([tx], fail_on={tx.txid})
    with pytest.raises(SourceError):
        await chain.get_tx(tx.txid)
    with pytest.raises(NotFound):
        await chain.get_tx("ff" * 32)
    with budget_scope(CallBudget(1)), pytest.raises(BudgetExceeded):
        await chain.tip_height()
        await chain.tip_height()
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain/test_client.py tests/test_fakes.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement the protocol and client**

`backend/btcintel/chain/source.py`:
```python
"""The data-source interface every analysis component depends on."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from btcintel.chain.models import AddressStats, Outspend, Tx


class ChainSource(Protocol):
    async def get_tx(self, txid: str) -> Tx: ...

    async def get_outspends(self, txid: str) -> list[Outspend]: ...

    async def get_address(self, address: str) -> AddressStats: ...

    async def get_address_txs(self, address: str, after_txid: str | None = None) -> list[Tx]: ...

    def iter_address_txs(self, address: str, max_txs: int = 1000) -> AsyncIterator[Tx]: ...

    async def tip_height(self) -> int: ...

    async def get_price_usd(self, ts: int) -> float | None: ...
```

`backend/btcintel/chain/client.py`:
```python
"""ChainSource over one or more Esplora backends with caching and failover."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, TypeVar

from btcintel.chain.cache import Cache
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.esplora_parse import parse_address, parse_outspends, parse_tx
from btcintel.chain.models import AddressStats, Outspend, Tx

T = TypeVar("T")

IMMUTABLE_CONFIRMATIONS = 6
SHALLOW_TX_TTL = 60.0
VOLATILE_TTL = 120.0


class ChainClient:
    def __init__(self, backends: Sequence[EsploraBackend], cache: Cache, *, tip_ttl: float = 30.0) -> None:
        if not backends:
            raise ValueError("at least one backend is required")
        self.backends = list(backends)
        self.cache = cache
        self.tip_ttl = tip_ttl

    def _ordered(self, need_price: bool) -> list[EsploraBackend]:
        candidates = [b for b in self.backends if b.supports_price or not need_price]
        return sorted(candidates, key=lambda b: b.bucket.next_available())  # stable: config order on ties

    async def _call(self, fn: Callable[[EsploraBackend], Awaitable[T]], *, need_price: bool = False) -> T:
        candidates = self._ordered(need_price)
        if not candidates:
            raise SourceError("no configured backend supports this request")
        errors = []
        for backend in candidates:
            try:
                return await fn(backend)
            except SourceError as e:
                errors.append(str(e))
        raise SourceError("all backends failed: " + "; ".join(errors))

    async def tip_height(self) -> int:
        cached = self.cache.get_json("tip")
        if cached is not None:
            return int(cached)
        height = int((await self._call(lambda b: b.get_text("/blocks/tip/height"))).strip())
        self.cache.put_json("tip", height, self.tip_ttl)
        return height

    async def _deep(self, height: int | None) -> bool:
        if height is None:
            return False
        return (await self.tip_height()) - height + 1 >= IMMUTABLE_CONFIRMATIONS

    async def _store_tx(self, raw: dict[str, Any]) -> None:
        status = raw.get("status") or {}
        deep = bool(status.get("confirmed")) and await self._deep(status.get("block_height"))
        self.cache.put_json(f"tx:{raw['txid']}", raw, None if deep else SHALLOW_TX_TTL)

    async def get_tx(self, txid: str) -> Tx:
        raw = self.cache.get_json(f"tx:{txid}")
        if raw is None:
            raw = await self._call(lambda b: b.get_json(f"/tx/{txid}"))
            await self._store_tx(raw)
        return parse_tx(raw)

    async def get_outspends(self, txid: str) -> list[Outspend]:
        key = f"outspends:{txid}"
        raw = self.cache.get_json(key)
        if raw is not None:
            return parse_outspends(raw)
        raw = await self._call(lambda b: b.get_json(f"/tx/{txid}/outspends"))
        spends = parse_outspends(raw)
        immutable = bool(spends)
        for o in spends:
            if not (o.spent and o.status and o.status.confirmed and await self._deep(o.status.block_height)):
                immutable = False
                break
        self.cache.put_json(key, raw, None if immutable else VOLATILE_TTL)
        return spends

    async def get_address(self, address: str) -> AddressStats:
        key = f"addr:{address}"
        raw = self.cache.get_json(key)
        if raw is None:
            raw = await self._call(lambda b: b.get_json(f"/address/{address}"))
            self.cache.put_json(key, raw, VOLATILE_TTL)
        return parse_address(raw)

    async def get_address_txs(self, address: str, after_txid: str | None = None) -> list[Tx]:
        path = f"/address/{address}/txs" + (f"/chain/{after_txid}" if after_txid else "")
        key = f"addrtxs:{address}:{after_txid or ''}"
        raw = self.cache.get_json(key)
        if raw is None:
            raw = await self._call(lambda b: b.get_json(path))
            self.cache.put_json(key, raw, VOLATILE_TTL)
            for tx_raw in raw:
                await self._store_tx(tx_raw)
        return [parse_tx(t) for t in raw]

    async def iter_address_txs(self, address: str, max_txs: int = 1000) -> AsyncIterator[Tx]:
        seen: set[str] = set()
        after: str | None = None
        while len(seen) < max_txs:
            page = await self.get_address_txs(address, after)
            fresh = [t for t in page if t.txid not in seen]
            if not fresh:
                return
            for tx in fresh:
                seen.add(tx.txid)
                yield tx
                if len(seen) >= max_txs:
                    return
            confirmed = [t for t in page if t.status.confirmed]
            if not confirmed:
                return
            after = confirmed[-1].txid

    async def get_price_usd(self, ts: int) -> float | None:
        hour = ts - ts % 3600
        key = f"price:USD:{hour}"
        cached = self.cache.get_json(key)
        if cached is not None:
            return float(cached)
        try:
            raw = await self._call(
                lambda b: b.get_json(f"/v1/historical-price?currency=USD&timestamp={hour}"),
                need_price=True,
            )
        except (NotFound, SourceError):
            return None
        prices = raw.get("prices") or []
        if not prices or "USD" not in prices[0]:
            return None
        usd = float(prices[0]["USD"])
        self.cache.put_json(key, usd, None)
        return usd
```

- [ ] **Step 3: Append `FakeChain` to `backend/tests/fakes.py`**

```python
from collections.abc import AsyncIterator, Iterable  # noqa: E402

from btcintel.chain.budget import charge_budget  # noqa: E402
from btcintel.chain.errors import NotFound, SourceError  # noqa: E402
from btcintel.chain.models import AddressStats, Outspend, Tx, TxStatus  # noqa: E402


class FakeChain:
    """In-memory ChainSource. Outspends and address histories are derived from held txs."""

    def __init__(self, txs: Iterable[Tx] = (), tip: int = 900_000, fail_on: Iterable[str] = ()) -> None:
        self.txs: dict[str, Tx] = {}
        self.tip = tip
        self.fail_on = set(fail_on)
        self.calls = 0
        self.add(*txs)

    def add(self, *txs: Tx) -> None:
        for tx in txs:
            self.txs[tx.txid] = tx

    def _charge(self, txid: str | None = None) -> None:
        self.calls += 1
        charge_budget()
        if txid is not None and txid in self.fail_on:
            raise SourceError(f"fake backend failure for {txid}")

    def _history(self, address: str) -> list[Tx]:
        return [
            t for t in self.txs.values()
            if address in t.input_addresses() or address in t.output_addresses()
        ]

    async def get_tx(self, txid: str) -> Tx:
        self._charge(txid)
        if txid not in self.txs:
            raise NotFound(txid)
        return self.txs[txid]

    async def get_outspends(self, txid: str) -> list[Outspend]:
        self._charge(txid)
        tx = self.txs.get(txid)
        if tx is None:
            raise NotFound(txid)
        spends = [Outspend(spent=False) for _ in tx.vout]
        for child in self.txs.values():
            for i in child.vin:
                if i.prev_txid == txid and i.prev_vout < len(spends):
                    spends[i.prev_vout] = Outspend(
                        spent=True, txid=child.txid, vin=i.n,
                        status=TxStatus(confirmed=True, block_height=child.status.block_height),
                    )
        return spends

    async def get_address(self, address: str) -> AddressStats:
        self._charge()
        hist = self._history(address)
        funded = [o for t in hist for o in t.vout if o.address == address]
        spent = [i for t in hist for i in t.vin if i.address == address]
        return AddressStats(
            address=address, tx_count=len(hist), funded_txo_count=len(funded),
            funded_sum=sum(o.value for o in funded), spent_txo_count=len(spent),
            spent_sum=sum(i.value for i in spent),
        )

    async def get_address_txs(self, address: str, after_txid: str | None = None) -> list[Tx]:
        self._charge()
        hist = self._history(address)
        ids = [t.txid for t in hist]
        start = ids.index(after_txid) + 1 if after_txid in ids else 0
        return hist[start : start + 25]

    async def iter_address_txs(self, address: str, max_txs: int = 1000) -> AsyncIterator[Tx]:
        for i, tx in enumerate(self._history(address)[:max_txs]):
            if i % 25 == 0:
                self._charge()
            yield tx

    async def tip_height(self) -> int:
        self._charge()
        return self.tip

    async def get_price_usd(self, ts: int) -> float | None:
        return None
```

- [ ] **Step 4: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/chain tests/test_fakes.py -v && uv run ruff check .`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/chain/source.py backend/btcintel/chain/client.py backend/tests/fakes.py backend/tests/chain/test_client.py backend/tests/test_fakes.py
git commit -m "feat(chain): ChainClient with reorg-safe cache policy, failover, pagination, price

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Intel database, taxonomy and tag store

**Files:**
- Create: `backend/btcintel/db.py`, `backend/btcintel/labels/__init__.py`, `backend/btcintel/labels/taxonomy.py`, `backend/btcintel/labels/store.py`
- Test: `backend/tests/test_db.py`, `backend/tests/labels/test_taxonomy.py`, `backend/tests/labels/test_store.py`

**Interfaces:**
- Consumes: the catalog `Category`, `RISK_ORDER` and `load_catalog` (Plan 1), and `normalize_address` (Plan 1).
- Produces:
  - `open_intel_db(path) -> sqlite3.Connection` (autocommit mode, `Row` factory, WAL, foreign keys on, schema created)
  - `transaction(conn)` context manager (re-entrant: a nested use joins the outer transaction)
  - `Taxonomy(categories)`, with:
    - `.from_catalog(cat)`
    - `.categories: dict[str, Category]`
    - `.normalize(concept: str | None) -> str | None`, which maps GraphSense concepts or our own IDs onto our IDs
    - `.risk(cid) -> str`, `.risk_of_tag(tag) -> str`, `.default_stop_categories() -> set[str]`
  - `CONFIDENCE_LEVELS: dict[str, int]` (the GraphSense confidence table)
  - `Tag` (frozen pydantic model): `id: int | None, address, label, category, abuse=None, actor=None, confidence="unknown", source, pack, is_cluster_definer=False, lastmod=None, created_by="import"`, with computed `confidence_level`
  - `TagStore(conn)` methods:
    - adding: `add(tag) -> int`, `add_many(tags) -> int`
    - lookup: `get(id)`, `for_address(a)`, `for_addresses(addrs) -> dict[str, list[Tag]]`
    - search and packs: `search(q, limit=50)`, `by_pack(pack)`, `packs() -> list[tuple[str,int]]`
    - deletion: `delete(id) -> bool`, `delete_pack(pack) -> int`
    - coinbase rules: `set_coinbase_rules(rules) -> int`, `coinbase_rules() -> list[tuple[str,str]]` (longest tag first)

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_db.py`:
```python
import pytest

from btcintel.db import open_intel_db, transaction


def test_schema_created(tmp_path):
    conn = open_intel_db(tmp_path / "x" / "intel.db")
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"tags", "coinbase_rules", "addr_cluster", "clusters", "cluster_links", "cases", "case_watch"} <= names


def test_transaction_rolls_back_on_error():
    conn = open_intel_db(":memory:")
    with pytest.raises(RuntimeError), transaction(conn):
        conn.execute("INSERT INTO coinbase_rules(tag, pool) VALUES ('/x/', 'X')")
        raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM coinbase_rules").fetchone()[0] == 0


def test_nested_transactions_commit_once():
    conn = open_intel_db(":memory:")
    with transaction(conn):
        with transaction(conn):
            conn.execute("INSERT INTO coinbase_rules(tag, pool) VALUES ('/a/', 'A')")
        conn.execute("INSERT INTO coinbase_rules(tag, pool) VALUES ('/b/', 'B')")
    assert conn.execute("SELECT COUNT(*) FROM coinbase_rules").fetchone()[0] == 2
    assert not conn.in_transaction
```

`backend/tests/labels/test_taxonomy.py`:
```python
from btcintel.catalog.loader import load_catalog
from btcintel.labels.store import Tag
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir


def tax() -> Taxonomy:
    return Taxonomy.from_catalog(load_catalog(catalog_dir()))


def test_normalize_graphsense_and_own_ids():
    t = tax()
    assert t.normalize("exchange") == "exchange"
    assert t.normalize("Mixing_Service") == "mixing_service"
    assert t.normalize("sanction") == "sanctioned"
    assert t.normalize("service_hack") == "theft"
    assert t.normalize("high_risk_exchange") == "high_risk_exchange"
    assert t.normalize("nonsense") is None and t.normalize(None) is None


def test_risk_levels():
    t = tax()
    assert t.risk("sanctioned") == "severe" and t.risk("exchange") == "low" and t.risk(None) == "none"
    tag = Tag(address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", label="x", category="exchange",
              abuse="sanctioned", source="s", pack="p")
    assert t.risk_of_tag(tag) == "severe"


def test_default_stop_categories():
    stops = tax().default_stop_categories()
    assert {"exchange", "mixing_service", "instant_exchange", "bridge"} <= stops
    assert "individual" not in stops and "sanctioned" not in stops
```

`backend/tests/labels/test_store.py`:
```python
from btcintel.db import open_intel_db
from btcintel.labels.store import CONFIDENCE_LEVELS, Tag, TagStore

A1 = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
BECH = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"


def store() -> TagStore:
    return TagStore(open_intel_db(":memory:"))


def tag(address=A1, label="Binance", pack="p1", **kw) -> Tag:
    return Tag(address=address, label=label, category=kw.pop("category", "exchange"),
               source="https://example.org", pack=pack, confidence=kw.pop("confidence", "authority_data"), **kw)


def test_add_and_lookup_normalises_bech32():
    s = store()
    tag_id = s.add(tag(address=BECH.upper()))
    got = s.for_address(BECH)
    assert len(got) == 1 and got[0].id == tag_id and got[0].address == BECH
    assert got[0].confidence_level == CONFIDENCE_LEVELS["authority_data"] == 60
    assert s.for_address(BECH.upper())[0].id == tag_id


def test_same_address_label_pack_is_replaced():
    s = store()
    s.add(tag(actor="old"))
    s.add(tag(actor="new"))
    got = s.for_address(A1)
    assert len(got) == 1 and got[0].actor == "new"


def test_for_addresses_handles_many():
    s = store()
    s.add_many([tag(address=A1), tag(address=BECH, label="Kraken")])
    many = [A1, BECH] + [f"1Fake{i}" for i in range(1200)]
    got = s.for_addresses(many)
    assert set(got) == {A1, BECH}


def test_search_packs_delete():
    s = store()
    s.add_many([tag(), tag(label="Lazarus Group", pack="ofac", category="individual"), tag(label="Other", pack="p2")])
    assert [t.label for t in s.search("lazarus")] == ["Lazarus Group"]
    assert dict(s.packs()) == {"ofac": 1, "p1": 1, "p2": 1}
    assert s.delete_pack("p2") == 1
    t = s.for_address(A1)[0]
    assert s.delete(t.id) and s.get(t.id) is None


def test_coinbase_rules_longest_first():
    s = store()
    assert s.set_coinbase_rules([("/F2Pool/", "F2Pool"), ("/F2Pool/xyz/", "Other"), ("", "Empty")]) == 2
    assert s.coinbase_rules() == [("/F2Pool/xyz/", "Other"), ("/F2Pool/", "F2Pool")]
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/test_db.py tests/labels -v`
Expected: FAIL.

- [ ] **Step 2: Implement the database module**

`backend/btcintel/db.py`:
```python
"""The intel database (labels, clusters, cases): one SQLite file, schema created on open."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY, address TEXT NOT NULL, label TEXT NOT NULL,
        category TEXT NOT NULL, abuse TEXT, actor TEXT, confidence TEXT NOT NULL,
        confidence_level INTEGER NOT NULL, source TEXT NOT NULL, pack TEXT NOT NULL,
        is_cluster_definer INTEGER NOT NULL DEFAULT 0, lastmod TEXT,
        created_by TEXT NOT NULL DEFAULT 'import', UNIQUE (address, label, pack))""",
    "CREATE INDEX IF NOT EXISTS tags_address ON tags (address)",
    "CREATE INDEX IF NOT EXISTS tags_label ON tags (label)",
    "CREATE TABLE IF NOT EXISTS coinbase_rules (tag TEXT PRIMARY KEY, pool TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS addr_cluster (address TEXT PRIMARY KEY, root TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS addr_cluster_root ON addr_cluster (root)",
    """CREATE TABLE IF NOT EXISTS clusters (
        root TEXT PRIMARY KEY, size INTEGER NOT NULL, partial INTEGER NOT NULL DEFAULT 1,
        capped INTEGER NOT NULL DEFAULT 0, expanded_at REAL, calls_used INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS cluster_links (
        a TEXT NOT NULL, b TEXT NOT NULL, txid TEXT NOT NULL, heuristic TEXT NOT NULL,
        PRIMARY KEY (a, b, txid))""",
    """CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
        graph TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS case_watch (
        case_id TEXT NOT NULL REFERENCES cases (id) ON DELETE CASCADE, address TEXT NOT NULL,
        added_at REAL NOT NULL, PRIMARY KEY (case_id, address))""",
]


def open_intel_db(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    for stmt in SCHEMA:
        conn.execute(stmt)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN/COMMIT (ROLLBACK on error). Nested use joins the outer transaction."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
```

- [ ] **Step 3: Implement the taxonomy and store**

`backend/btcintel/labels/__init__.py`: empty.

`backend/btcintel/labels/store.py`:
```python
"""Attribution tags (address → label/category/abuse) with provenance and confidence."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, computed_field

from btcintel.chain.validate import normalize_address
from btcintel.db import transaction

# GraphSense TagPack confidence taxonomy (graphsense-lib tagpack/db/confidence.csv)
CONFIDENCE_LEVELS: dict[str, int] = {
    "override": 100, "ownership": 100, "ledger_immanent": 100, "manual_transaction": 90,
    "service_api": 70, "forensic_investigation": 70, "authority_data": 60, "trusted_provider": 50,
    "service_data": 50, "forensic": 50, "untrusted_transaction": 40, "web_crawl": 20,
    "heuristic": 10, "unknown": 5,
}

_COLUMNS = (
    "address", "label", "category", "abuse", "actor", "confidence", "confidence_level", "source",
    "pack", "is_cluster_definer", "lastmod", "created_by",
)


class Tag(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    address: str
    label: str
    category: str
    abuse: str | None = None
    actor: str | None = None
    confidence: str = "unknown"
    source: str
    pack: str
    is_cluster_definer: bool = False
    lastmod: str | None = None
    created_by: str = "import"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confidence_level(self) -> int:
        return CONFIDENCE_LEVELS.get(self.confidence, 5)


def _row(t: Tag) -> tuple:
    return (
        normalize_address(t.address), t.label, t.category, t.abuse, t.actor, t.confidence,
        t.confidence_level, t.source, t.pack, int(t.is_cluster_definer), t.lastmod, t.created_by,
    )


def _tag(r: sqlite3.Row) -> Tag:
    return Tag(
        id=r["id"], address=r["address"], label=r["label"], category=r["category"], abuse=r["abuse"],
        actor=r["actor"], confidence=r["confidence"], source=r["source"], pack=r["pack"],
        is_cluster_definer=bool(r["is_cluster_definer"]), lastmod=r["lastmod"],
        created_by=r["created_by"],
    )


class TagStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def add(self, tag: Tag) -> int:
        cur = self.conn.execute(
            f"INSERT OR REPLACE INTO tags ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' * len(_COLUMNS))})",
            _row(tag),
        )
        return int(cur.lastrowid)

    def add_many(self, tags: Iterable[Tag]) -> int:
        rows = [_row(t) for t in tags]
        with transaction(self.conn):
            self.conn.executemany(
                f"INSERT OR REPLACE INTO tags ({', '.join(_COLUMNS)}) "
                f"VALUES ({', '.join('?' * len(_COLUMNS))})",
                rows,
            )
        return len(rows)

    def get(self, tag_id: int) -> Tag | None:
        r = self.conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        return _tag(r) if r else None

    def for_address(self, address: str) -> list[Tag]:
        rows = self.conn.execute(
            "SELECT * FROM tags WHERE address = ? ORDER BY confidence_level DESC, label",
            (normalize_address(address),),
        )
        return [_tag(r) for r in rows]

    def for_addresses(self, addresses: Iterable[str]) -> dict[str, list[Tag]]:
        wanted = list(dict.fromkeys(normalize_address(a) for a in addresses))
        out: dict[str, list[Tag]] = {}
        for i in range(0, len(wanted), 500):
            chunk = wanted[i : i + 500]
            rows = self.conn.execute(
                f"SELECT * FROM tags WHERE address IN ({', '.join('?' * len(chunk))}) "
                "ORDER BY confidence_level DESC, label",
                chunk,
            )
            for r in rows:
                out.setdefault(r["address"], []).append(_tag(r))
        return out

    def search(self, q: str, limit: int = 50) -> list[Tag]:
        like = f"%{q}%"
        rows = self.conn.execute(
            "SELECT * FROM tags WHERE label LIKE ? OR actor LIKE ? OR address = ? "
            "ORDER BY confidence_level DESC, label LIMIT ?",
            (like, like, q, limit),
        )
        return [_tag(r) for r in rows]

    def by_pack(self, pack: str) -> list[Tag]:
        return [_tag(r) for r in self.conn.execute("SELECT * FROM tags WHERE pack = ? ORDER BY id", (pack,))]

    def packs(self) -> list[tuple[str, int]]:
        rows = self.conn.execute("SELECT pack, COUNT(*) AS n FROM tags GROUP BY pack ORDER BY pack")
        return [(r["pack"], r["n"]) for r in rows]

    def delete(self, tag_id: int) -> bool:
        return self.conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,)).rowcount > 0

    def delete_pack(self, pack: str) -> int:
        return self.conn.execute("DELETE FROM tags WHERE pack = ?", (pack,)).rowcount

    def set_coinbase_rules(self, rules: Iterable[tuple[str, str]]) -> int:
        clean = {tag: pool for tag, pool in rules if tag}
        with transaction(self.conn):
            self.conn.execute("DELETE FROM coinbase_rules")
            self.conn.executemany("INSERT INTO coinbase_rules (tag, pool) VALUES (?, ?)", clean.items())
        return len(clean)

    def coinbase_rules(self) -> list[tuple[str, str]]:
        rows = self.conn.execute("SELECT tag, pool FROM coinbase_rules ORDER BY length(tag) DESC, tag")
        return [(r["tag"], r["pool"]) for r in rows]
```

`backend/btcintel/labels/taxonomy.py`:
```python
"""Category taxonomy from the catalog: GraphSense concept mapping and risk levels."""

from __future__ import annotations

from collections.abc import Iterable

from btcintel.catalog.schema import RISK_ORDER, Catalog, Category
from btcintel.labels.store import Tag


class Taxonomy:
    def __init__(self, categories: Iterable[Category]) -> None:
        self.categories: dict[str, Category] = {c.id: c for c in categories}
        self._by_concept = {gs.lower(): c.id for c in self.categories.values() for gs in c.gs_concepts}

    @classmethod
    def from_catalog(cls, cat: Catalog) -> Taxonomy:
        return cls(cat.categories)

    def normalize(self, concept: str | None) -> str | None:
        if not concept:
            return None
        key = str(concept).strip().lower()
        if key in self.categories:
            return key
        return self._by_concept.get(key)

    def risk(self, category_id: str | None) -> str:
        c = self.categories.get(category_id or "")
        return c.risk if c else "none"

    def risk_of_tag(self, tag: Tag) -> str:
        return max((self.risk(tag.category), self.risk(tag.abuse)), key=RISK_ORDER.__getitem__)

    def default_stop_categories(self) -> set[str]:
        return {c.id for c in self.categories.values() if c.stop_trace}
```

- [ ] **Step 4: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/test_db.py tests/labels -v && uv run ruff check .`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/db.py backend/btcintel/labels backend/tests/test_db.py backend/tests/labels
git commit -m "feat(labels): intel database, taxonomy with GraphSense mapping, tag store

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Label importers (GraphSense TagPacks, OFAC SDN, mining pools, ransomwhe.re) + CLI

**Files:**
- Create: `backend/btcintel/labels/tagpack.py`, `backend/btcintel/labels/ofac.py`, `backend/btcintel/labels/pools.py`, `backend/btcintel/labels/ransomwhere.py`, `backend/btcintel/labels/importers.py`
- Modify: `backend/btcintel/cli.py` (add `import-tags` and `tags`)
- Test: `backend/tests/labels/test_importers.py`, `backend/tests/test_cli_tags.py`

**Interfaces:**
- Consumes: `Tag`, `TagStore`, `Taxonomy` (Task 7); `is_address`, `normalize_address`; `load_settings`; `open_intel_db`.
- Produces:
  - `parse_tagpack(text: str, pack: str, taxonomy: Taxonomy) -> tuple[list[Tag], list[str]]` (tags, warnings); raises `ValueError` for non-TagPacks
  - `export_tagpack(tags: list[Tag], title: str, creator: str) -> str`
  - `parse_sdn_xml(source: BinaryIO | str | Path) -> tuple[list[Tag], str | None]` (tags, publish date as ISO)
  - `parse_pools(text: str) -> tuple[list[Tag], list[tuple[str,str]]]` (address tags, coinbase tag rules)
  - `parse_ransomwhere(text: str) -> list[Tag]`
  - `ImportReport(packs=0, tags=0, warnings=[], errors=[])` dataclass
  - `import_tagpack_text(store, taxonomy, text, pack) -> ImportReport`, `import_graphsense_tarball(store, taxonomy, data: bytes) -> ImportReport`, `import_ofac(store, data: bytes)`, `import_pools(store, data: bytes)`, `import_ransomwhere(store, data: bytes)`
  - URLs `GRAPHSENSE_TARBALL_URL`, `OFAC_SDN_URL`, `POOLS_URL`, `RANSOMWHERE_URL`; `fetch(url: str, proxy: str | None) -> bytes`
  - CLI: `btcintel import-tags {graphsense|ofac|pools|ransomwhere}`, `btcintel import-tags tagpack PATH [--pack NAME]`, `btcintel tags ADDRESS`

Formats were verified on 2026-09-25:
- **GraphSense TagPacks:** header fields are defaults for each tag; tag-level fields override them. A `currency`/`network` of `BTC` selects Bitcoin. `category` holds entity concepts and `abuse` holds abuse concepts.
- **OFAC SDN.XML:** namespace `https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML`; `sdnEntry/idList/id/idType == "Digital Currency Address - XBT"`, with the address in `idNumber`.
- **mempool pools-v2.json:** a list of `{id, name, addresses[], tags[], link}`.
- **ransomwhe.re export:** `{"result": [{address, blockchain, family, ...}]}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/labels/test_importers.py`:
```python
import io
import json
import tarfile

import pytest

from btcintel.catalog.loader import load_catalog
from btcintel.db import open_intel_db
from btcintel.labels.importers import (
    import_graphsense_tarball,
    import_ofac,
    import_pools,
    import_ransomwhere,
    import_tagpack_text,
)
from btcintel.labels.ofac import parse_sdn_xml
from btcintel.labels.pools import parse_pools
from btcintel.labels.ransomwhere import parse_ransomwhere
from btcintel.labels.store import TagStore
from btcintel.labels.tagpack import export_tagpack, parse_tagpack
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))
BLENDER_1 = "3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4"
BLENDER_2 = "32fbAZMTaQxNd2fAue1PgsiPgWfcsHBQQt"

TAGPACK = f"""
title: Blender.io
creator: GraphSense Core Team
confidence: authority_data
category: mixing_service
currency: BTC
label: Blender.io
source: https://home.treasury.gov/policy-issues/financial-sanctions/recent-actions/20220506
actor: blenderio
tags:
- address: {BLENDER_1}
- address: {BLENDER_2}
  label: Blender.io hot wallet
  abuse: sanction
- address: 0x252a8bd2319d8a555b872990601221b3a2053bce
  currency: ETH
- address: 1NotARealAddressxxxxxxxxxxxxxxxx
- address: bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6
  category: something_new
"""


def test_parse_tagpack_defaults_overrides_and_filters():
    tags, warnings = parse_tagpack(TAGPACK, "gs:blender_io", TAX)
    by_addr = {t.address: t for t in tags}
    assert set(by_addr) == {BLENDER_1, BLENDER_2, "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"}
    t1 = by_addr[BLENDER_1]
    assert (t1.label, t1.category, t1.actor, t1.confidence, t1.pack) == (
        "Blender.io", "mixing_service", "blenderio", "authority_data", "gs:blender_io",
    )
    t2 = by_addr[BLENDER_2]
    assert t2.label == "Blender.io hot wallet" and t2.abuse == "sanctioned"
    assert by_addr["bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"].category == "unknown"
    assert any("invalid BTC address" in w for w in warnings)
    assert any("something_new" in w for w in warnings)


def test_parse_tagpack_rejects_non_tagpack():
    with pytest.raises(ValueError, match="not a TagPack"):
        parse_tagpack("just: a mapping\n", "x", TAX)


def test_export_roundtrip():
    tags, _ = parse_tagpack(TAGPACK, "gs:blender_io", TAX)
    text = export_tagpack(tags, title="t", creator="c")
    again, warnings = parse_tagpack(text, "roundtrip", TAX)
    assert {(t.address, t.label, t.category, t.abuse) for t in again} == {
        (t.address, t.label, t.category, t.abuse) for t in tags
    }
    assert warnings == []


SDN = b"""<?xml version="1.0" standalone="yes"?>
<sdnList xmlns="https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/XML">
  <publshInformation><Publish_Date>09/23/2026</Publish_Date><Record_Count>2</Record_Count></publshInformation>
  <sdnEntry>
    <uid>24003</uid><firstName>Behzad</firstName><lastName>MESRI</lastName><sdnType>Individual</sdnType>
    <programList><program>CYBER2</program></programList>
    <idList>
      <id><uid>1</uid><idType>Digital Currency Address - XBT</idType><idNumber>12aNKp2iDKuhEde2YfPdd4DFGenRUTKupL</idNumber></id>
      <id><uid>2</uid><idType>Digital Currency Address - ETH</idType><idNumber>0x252a8bd2319d8a555b872990601221b3a2053bce</idNumber></id>
      <id><uid>3</uid><idType>Digital Currency Address - XBT</idType><idNumber>not-an-address</idNumber></id>
    </idList>
  </sdnEntry>
  <sdnEntry>
    <uid>99</uid><lastName>BLENDER.IO</lastName><sdnType>Entity</sdnType>
    <idList><id><uid>4</uid><idType>Digital Currency Address - XBT</idType><idNumber>3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4</idNumber></id></idList>
  </sdnEntry>
</sdnList>"""


def test_parse_sdn_xml():
    tags, published = parse_sdn_xml(io.BytesIO(SDN))
    assert published == "2026-09-23"
    assert [(t.address, t.label, t.category, t.abuse) for t in tags] == [
        ("12aNKp2iDKuhEde2YfPdd4DFGenRUTKupL", "Behzad MESRI", "individual", "sanctioned"),
        ("3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4", "BLENDER.IO", "organization", "sanctioned"),
    ]
    assert all(t.confidence == "authority_data" and t.pack == "ofac_sdn" for t in tags)
    assert tags[0].source.endswith("#uid=24003")


POOLS = json.dumps([
    {"id": 1, "name": "BlockFills", "addresses": ["1PzVut5X6Nx7Mv4JHHKPtVM9Jr9LJ4Rbry"],
     "tags": ["/BlockfillsPool/"], "link": "https://www.blockfills.com/mining"},
    {"id": 2, "name": "ViaBTC", "addresses": [], "tags": ["/ViaBTC/", "viabtc.com deploy"], "link": ""},
])


def test_parse_pools():
    tags, rules = parse_pools(POOLS)
    assert [(t.address, t.label, t.category) for t in tags] == [
        ("1PzVut5X6Nx7Mv4JHHKPtVM9Jr9LJ4Rbry", "BlockFills", "mining_pool")
    ]
    assert ("/ViaBTC/", "ViaBTC") in rules and len(rules) == 3


RANSOM = json.dumps({"result": [
    {"address": "17TMc2UkVRSga2yYvuxSD9Q1XyB2EPRjTF", "blockchain": "bitcoin", "family": "Netwalker (Mailto)"},
    {"address": "0xabc", "blockchain": "ethereum", "family": "X"},
]})


def test_parse_ransomwhere():
    (t,) = parse_ransomwhere(RANSOM)
    assert (t.address, t.label, t.category, t.abuse, t.pack) == (
        "17TMc2UkVRSga2yYvuxSD9Q1XyB2EPRjTF", "Netwalker (Mailto)", "perpetrator", "ransomware", "ransomwhere",
    )


def _tarball(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_import_functions_store_tags():
    store = TagStore(open_intel_db(":memory:"))
    rep = import_tagpack_text(store, TAX, TAGPACK, "gs:blender_io")
    assert rep.tags == 3 and rep.packs == 1
    data = _tarball({
        "graphsense-tagpacks-master/packs/blender_io.yaml": TAGPACK,
        "graphsense-tagpacks-master/packs/eth_only.yaml": "title: e\ncreator: c\ncurrency: ETH\nlabel: x\nsource: s\ntags:\n- address: '0xabc'\n",
        "graphsense-tagpacks-master/packs/broken.yaml": "tags: [unclosed\n",
        "graphsense-tagpacks-master/README.md": "not a pack",
    })
    rep = import_graphsense_tarball(store, TAX, data)
    assert rep.packs == 3 and rep.tags == 3 and len(rep.errors) == 1
    assert import_ofac(store, SDN).tags == 2
    rep = import_pools(store, POOLS.encode())
    assert rep.tags == 1 and store.coinbase_rules()[0][1] in {"ViaBTC", "BlockFills"}
    assert import_ransomwhere(store, RANSOM.encode()).tags == 1
    assert {p for p, _ in store.packs()} == {"gs:blender_io", "ofac_sdn", "mempool_pools", "ransomwhere"}
```

`backend/tests/test_cli_tags.py`:
```python
from btcintel.cli import main
from tests.labels.test_importers import TAGPACK


def test_import_tagpack_file_then_query(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BTCINTEL_DATA_DIR", str(tmp_path / "data"))
    pack = tmp_path / "blender.yaml"
    pack.write_text(TAGPACK)
    assert main(["import-tags", "tagpack", str(pack), "--pack", "blender"]) == 0
    assert "3 tags" in capsys.readouterr().out
    assert main(["tags", "3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4"]) == 0
    out = capsys.readouterr().out
    assert "Blender.io" in out and "mixing_service" in out
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/labels/test_importers.py tests/test_cli_tags.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement the parsers**

`backend/btcintel/labels/tagpack.py`:
```python
"""GraphSense TagPack import/export (https://github.com/graphsense/graphsense-tagpacks)."""

from __future__ import annotations

from typing import Any

import yaml

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag
from btcintel.labels.taxonomy import Taxonomy

_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def parse_tagpack(text: str, pack: str, taxonomy: Taxonomy) -> tuple[list[Tag], list[str]]:
    doc = yaml.load(text, Loader=_Loader)  # noqa: S506 - safe loader
    if not isinstance(doc, dict) or not isinstance(doc.get("tags"), list):
        raise ValueError(f"{pack}: not a TagPack (missing 'tags' list)")
    header = {k: v for k, v in doc.items() if k != "tags"}
    tags: list[Tag] = []
    warnings: list[str] = []
    for i, raw in enumerate(doc["tags"]):
        if not isinstance(raw, dict):
            warnings.append(f"{pack} tag #{i}: not a mapping")
            continue
        t = {**header, **raw}
        currency = str(t.get("currency") or t.get("network") or "").upper()
        address = str(t.get("address") or "").strip()
        if currency != "BTC" or not address:
            continue
        if not is_address(address):
            warnings.append(f"{pack} tag #{i}: invalid BTC address {address!r}")
            continue
        label, source = t.get("label"), t.get("source")
        if not label or not source:
            warnings.append(f"{pack} tag #{i}: missing label or source")
            continue
        raw_category = t.get("category") or _first(t.get("concepts"))
        category = taxonomy.normalize(raw_category)
        if category is None:
            if raw_category:
                warnings.append(f"{pack} tag #{i}: unknown category {raw_category!r}")
            category = "unknown"
        abuse = taxonomy.normalize(t.get("abuse")) if t.get("abuse") else None
        if t.get("abuse") and abuse is None:
            warnings.append(f"{pack} tag #{i}: unknown abuse {t.get('abuse')!r}")
        tags.append(
            Tag(
                address=normalize_address(address), label=str(label), category=category, abuse=abuse,
                actor=str(t["actor"]) if t.get("actor") else None,
                confidence=str(t.get("confidence") or "unknown"), source=str(source), pack=pack,
                is_cluster_definer=bool(t.get("is_cluster_definer", False)),
                lastmod=str(t["lastmod"]) if t.get("lastmod") else None,
            )
        )
    return tags, warnings


def export_tagpack(tags: list[Tag], title: str, creator: str) -> str:
    entries = []
    for t in tags:
        entry = {
            "address": t.address, "label": t.label, "category": t.category, "abuse": t.abuse,
            "actor": t.actor, "source": t.source, "confidence": t.confidence, "lastmod": t.lastmod,
        }
        entries.append({k: v for k, v in entry.items() if v is not None})
    doc = {"title": title, "creator": creator, "currency": "BTC", "network": "BTC",
           "is_public": False, "tags": entries}
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
```

`backend/btcintel/labels/ofac.py`:
```python
"""OFAC SDN list (SDN.XML) → sanctioned Bitcoin address tags."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag

OFAC_SDN_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"
XBT = "Digital Currency Address - XBT"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(elem: ET.Element, name: str) -> str | None:
    for child in elem:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return None


def _iso(date: str) -> str | None:
    try:
        return datetime.strptime(date, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def parse_sdn_xml(source: BinaryIO | str | Path) -> tuple[list[Tag], str | None]:
    tags: list[Tag] = []
    published: str | None = None
    for _, elem in ET.iterparse(source, events=("end",)):
        name = _local(elem.tag)
        if name == "Publish_Date":
            published = _iso((elem.text or "").strip())
        elif name == "sdnEntry":
            label = " ".join(filter(None, [_child_text(elem, "firstName"), _child_text(elem, "lastName")]))
            category = "individual" if _child_text(elem, "sdnType") == "Individual" else "organization"
            uid = _child_text(elem, "uid")
            for id_el in (e for e in elem.iter() if _local(e.tag) == "id"):
                address = (_child_text(id_el, "idNumber") or "").strip()
                if _child_text(id_el, "idType") == XBT and is_address(address):
                    tags.append(Tag(
                        address=normalize_address(address), label=label or "OFAC SDN entry",
                        category=category, abuse="sanctioned", confidence="authority_data",
                        source=f"{OFAC_SDN_URL}#uid={uid}", pack="ofac_sdn", lastmod=published,
                    ))
            elem.clear()
    return tags, published
```

`backend/btcintel/labels/pools.py`:
```python
"""mempool/mining-pools pools-v2.json → pool payout-address tags and coinbase tag rules."""

from __future__ import annotations

import json

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag

POOLS_URL = "https://raw.githubusercontent.com/mempool/mining-pools/master/pools-v2.json"


def parse_pools(text: str) -> tuple[list[Tag], list[tuple[str, str]]]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("pools-v2.json: expected a list of pools")
    tags: list[Tag] = []
    rules: list[tuple[str, str]] = []
    for pool in data:
        name = str(pool["name"])
        for address in pool.get("addresses", []):
            if is_address(address):
                tags.append(Tag(
                    address=normalize_address(address), label=name, category="mining_pool",
                    confidence="trusted_provider", source=pool.get("link") or POOLS_URL,
                    pack="mempool_pools",
                ))
        rules.extend((str(tag), name) for tag in pool.get("tags", []) if tag)
    return tags, rules
```

`backend/btcintel/labels/ransomwhere.py`:
```python
"""ransomwhe.re export → ransomware payment address tags."""

from __future__ import annotations

import json

from btcintel.chain.validate import is_address, normalize_address
from btcintel.labels.store import Tag

RANSOMWHERE_URL = "https://api.ransomwhe.re/export"


def parse_ransomwhere(text: str) -> list[Tag]:
    data = json.loads(text)
    rows = data["result"] if isinstance(data, dict) else data
    tags = []
    for r in rows:
        address = str(r.get("address") or "").strip()
        if r.get("blockchain") != "bitcoin" or not is_address(address):
            continue
        tags.append(Tag(
            address=normalize_address(address), label=str(r.get("family") or "Unknown ransomware"),
            category="perpetrator", abuse="ransomware", confidence="forensic",
            source="https://ransomwhe.re/", pack="ransomwhere",
        ))
    return tags
```

`backend/btcintel/labels/importers.py`:
```python
"""Download-and-import helpers used by the CLI and API."""

from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import httpx
import yaml

from btcintel.labels.ofac import OFAC_SDN_URL, parse_sdn_xml
from btcintel.labels.pools import POOLS_URL, parse_pools
from btcintel.labels.ransomwhere import RANSOMWHERE_URL, parse_ransomwhere
from btcintel.labels.store import TagStore
from btcintel.labels.tagpack import parse_tagpack
from btcintel.labels.taxonomy import Taxonomy

GRAPHSENSE_TARBALL_URL = "https://codeload.github.com/graphsense/graphsense-tagpacks/tar.gz/refs/heads/master"

__all__ = [
    "GRAPHSENSE_TARBALL_URL", "OFAC_SDN_URL", "POOLS_URL", "RANSOMWHERE_URL", "ImportReport",
    "fetch", "import_graphsense_tarball", "import_ofac", "import_pools", "import_ransomwhere",
    "import_tagpack_text",
]


@dataclass
class ImportReport:
    packs: int = 0
    tags: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def fetch(url: str, proxy: str | None = None, timeout: float = 300.0) -> bytes:
    resp = httpx.get(url, proxy=proxy, timeout=timeout, follow_redirects=True,
                     headers={"User-Agent": "btc-intel-importer/0.1"})
    resp.raise_for_status()
    return resp.content


def import_tagpack_text(store: TagStore, taxonomy: Taxonomy, text: str, pack: str) -> ImportReport:
    tags, warnings = parse_tagpack(text, pack, taxonomy)
    store.delete_pack(pack)
    return ImportReport(packs=1, tags=store.add_many(tags), warnings=warnings)


def import_graphsense_tarball(store: TagStore, taxonomy: Taxonomy, data: bytes) -> ImportReport:
    """Import every packs/*.yaml from a GraphSense TagPacks tarball (read in memory, never extracted)."""
    report = ImportReport()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if not member.isfile() or "packs" not in path.parts or path.suffix != ".yaml":
                continue
            pack = f"gs:{path.stem}"
            text = tar.extractfile(member).read().decode("utf-8", errors="replace")  # type: ignore[union-attr]
            report.packs += 1
            try:
                sub = import_tagpack_text(store, taxonomy, text, pack)
            except (ValueError, yaml.YAMLError) as e:
                report.errors.append(f"{pack}: {e}")
                continue
            report.tags += sub.tags
            report.warnings += sub.warnings
    return report


def import_ofac(store: TagStore, data: bytes) -> ImportReport:
    tags, _ = parse_sdn_xml(io.BytesIO(data))
    store.delete_pack("ofac_sdn")
    return ImportReport(packs=1, tags=store.add_many(tags))


def import_pools(store: TagStore, data: bytes) -> ImportReport:
    tags, rules = parse_pools(data.decode())
    store.delete_pack("mempool_pools")
    report = ImportReport(packs=1, tags=store.add_many(tags))
    store.set_coinbase_rules(rules)
    return report


def import_ransomwhere(store: TagStore, data: bytes) -> ImportReport:
    tags = parse_ransomwhere(data.decode())
    store.delete_pack("ransomwhere")
    return ImportReport(packs=1, tags=store.add_many(tags))
```

- [ ] **Step 3: Add the CLI commands**

In `backend/btcintel/cli.py` add these imports:
```python
from pathlib import Path

from btcintel.config import load_settings
from btcintel.db import open_intel_db
from btcintel.labels import importers
from btcintel.labels.store import TagStore
from btcintel.labels.taxonomy import Taxonomy
```
Add these handlers:
```python
def _label_env():
    settings = load_settings()
    store = TagStore(open_intel_db(settings.intel_path))
    taxonomy = Taxonomy.from_catalog(load_catalog(settings.catalog_dir))
    return settings, store, taxonomy


def _cmd_import_tags(args: argparse.Namespace) -> int:
    settings, store, taxonomy = _label_env()
    source = args.source
    if source == "tagpack":
        path = Path(args.path)
        report = importers.import_tagpack_text(store, taxonomy, path.read_text(encoding="utf-8"),
                                               args.pack or f"file:{path.stem}")
    else:
        url = {"graphsense": importers.GRAPHSENSE_TARBALL_URL, "ofac": importers.OFAC_SDN_URL,
               "pools": importers.POOLS_URL, "ransomwhere": importers.RANSOMWHERE_URL}[source]
        print(f"downloading {url} …", file=sys.stderr)
        data = importers.fetch(url, proxy=settings.proxy)
        report = {
            "graphsense": lambda: importers.import_graphsense_tarball(store, taxonomy, data),
            "ofac": lambda: importers.import_ofac(store, data),
            "pools": lambda: importers.import_pools(store, data),
            "ransomwhere": lambda: importers.import_ransomwhere(store, data),
        }[source]()
    print(f"imported {report.tags} tags from {report.packs} pack(s); "
          f"{len(report.warnings)} warning(s), {len(report.errors)} error(s)")
    for line in (report.errors + report.warnings)[:20]:
        print(f"  {line}", file=sys.stderr)
    return 0


def _cmd_tags(args: argparse.Namespace) -> int:
    _, store, taxonomy = _label_env()
    tags = store.for_address(args.address)
    for t in tags:
        print(f"{t.label}\t{t.category}\t{t.abuse or '-'}\trisk={taxonomy.risk_of_tag(t)}\t"
              f"{t.confidence}\t{t.pack}\t{t.source}")
    if not tags:
        print("no tags")
    return 0


COMMANDS.update({"import-tags": _cmd_import_tags, "tags": _cmd_tags})
```
In `_build_parser()` add:
```python
    imp = sub.add_parser("import-tags", help="import attribution tags")
    imp.add_argument("source", choices=["graphsense", "ofac", "pools", "ransomwhere", "tagpack"])
    imp.add_argument("path", nargs="?", help="TagPack YAML file (source=tagpack)")
    imp.add_argument("--pack", help="pack name for a TagPack file")
    tg = sub.add_parser("tags", help="show tags for an address")
    tg.add_argument("address")
```
In `_cmd_import_tags`, when `source == "tagpack"` and `args.path` is missing, print `a TagPack path is required` to stderr and return 2.

- [ ] **Step 4: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/labels tests/test_cli_tags.py -v && uv run ruff check .`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/labels backend/btcintel/cli.py backend/tests/labels/test_importers.py backend/tests/test_cli_tags.py
git commit -m "feat(labels): GraphSense TagPack, OFAC SDN, mining-pool and ransomwhe.re importers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Smoke-import the live sources (manual, network)**

```bash
cd /home/fancybear/btc-intel/backend
uv run btcintel import-tags pools && uv run btcintel import-tags ofac && uv run btcintel import-tags ransomwhere && uv run btcintel import-tags graphsense
uv run btcintel tags 3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4
```
Expected:
- each import reports a nonzero tag count
- OFAC reports roughly 500 or more XBT addresses (534 on the 2026-09-23 list)
- the Blender.io address shows GraphSense and OFAC tags

Do not commit anything in `data/`; it is gitignored.

---

### Task 9: Heuristic framework (Finding, Context, registry) + wallet fingerprinting (H-FP)

**Files:**
- Create: `backend/btcintel/heuristics/__init__.py`, `backend/btcintel/heuristics/base.py`, `backend/btcintel/heuristics/fingerprint.py`, `backend/btcintel/heuristics/all.py`
- Modify: `catalog/heuristics.yaml` (H-FP → implemented), `docs/kb/heuristics/h-fp.md` ("Detection in btc-intel"), regenerated `docs/kb/index.md`
- Test: `backend/tests/heuristics/test_base.py`, `backend/tests/heuristics/test_fingerprint.py`, `backend/tests/heuristics/test_registry_catalog.py`

**Interfaces:**
- Consumes: `Tx`, `Outspend`, `ChainSource`, `ChainError`.
- Produces:
  - `Finding(heuristic: str, subject: str, label: str, confidence: float in [0,1], evidence: dict)` (frozen)
  - `tx_subject(txid) -> "tx:<txid>"`, `out_subject(txid, n) -> "out:<txid>:<n>"`
  - `Context(chain: ChainSource | None = None, coinbase_rules: list[tuple[str,str]] = [])`, with `async outspends(txid)` and `async tx(txid)`, each returning `None` without a chain
  - `HeuristicFn = Callable[[Tx, Context], Awaitable[list[Finding]]]`
  - the `heuristic(hid)` decorator
  - `registry() -> dict[str, HeuristicFn]`, which imports `btcintel.heuristics.all`
  - `analyze_tx(tx, ctx, only=None, heuristics=None) -> list[Finding]`, which turns a `ChainError` inside a detector into a `label="incomplete"` finding
  - `Fingerprint` dataclass: `version, locktime, locktime_kind, anti_fee_sniping, rbf, sequences, input_types, output_types, bip69, ecdsa_sigs, high_r_sigs, low_r_only, uncompressed_pubkey, has_op_return, feerate_int`, with `.signature() -> str` and `.as_dict()`
  - `fingerprint(tx: Tx) -> Fingerprint`
  - `fingerprint_heuristic`, registered as `H-FP`

Fingerprint rules:
- `locktime_kind` is `"zero"`, `"height"` (< 500,000,000) or `"time"`.
- `anti_fee_sniping` is `True` when the kind is height, the tx is confirmed and `1 ≤ block_height − locktime ≤ 2016`; `None` when unconfirmed.
- `rbf` is `True` when any input's nSequence < 0xFFFFFFFE (BIP125).
- `bip69` is `None` when there is at most one input and at most one output. Otherwise it is whether inputs are sorted by `(prev_txid, prev_vout)` and outputs by `(value, script bytes)`.
- A DER ECDSA signature is a pushed element with `b[0] == 0x30` and `b[1] == len(b) - 3` (the element includes the sighash byte). High-R means `b[3] == 33`.
- `low_r_only` is `None` when there are no ECDSA signatures.
- An uncompressed pubkey is a 65-byte element starting with `0x04`.
- `feerate_int` is whether `fee % vsize == 0` (`None` for coinbase).
- `signature()` covers `version|locktime_kind|rbf|input_types`. Ordering and R-values are left out because they depend on transaction shape rather than wallet choice.

- [ ] **Step 1: Write the failing tests**

`backend/tests/heuristics/test_base.py`:
```python
import pytest

from btcintel.chain.errors import SourceError
from btcintel.heuristics.base import Context, Finding, analyze_tx, heuristic, out_subject, tx_subject
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
```

`backend/tests/heuristics/test_fingerprint.py`:
```python
import json
from pathlib import Path

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.base import Context
from btcintel.heuristics.fingerprint import fingerprint, fingerprint_heuristic
from tests.builders import mk_tx

A = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
B = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"


def der_sig(high_r: bool) -> str:
    r = (b"\x00\x80" + b"\x11" * 31) if high_r else b"\x11" * 32
    s = b"\x22" * 32
    body = b"\x02" + bytes([len(r)]) + r + b"\x02" + bytes([len(s)]) + s
    return (b"\x30" + bytes([len(body)]) + body + b"\x01").hex()


PUB = "02" + "33" * 32
UNCOMPRESSED = "04" + "44" * 64


def test_locktime_kinds_and_anti_fee_sniping():
    zero = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=0, height=900_000))
    assert zero.locktime_kind == "zero" and zero.anti_fee_sniping is False
    afs = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=899_990, height=900_000))
    assert afs.locktime_kind == "height" and afs.anti_fee_sniping is True
    old = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=850_000, height=900_000))
    assert old.anti_fee_sniping is False
    unconf = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=899_990, confirmed=False))
    assert unconf.anti_fee_sniping is None
    timed = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], locktime=1_700_000_000))
    assert timed.locktime_kind == "time"


def test_rbf_and_sequences():
    fp = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], sequence=0xFFFFFFFD))
    assert fp.rbf and fp.sequences == ("fffffffd",)
    assert not fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], sequence=0xFFFFFFFE)).rbf


def test_bip69():
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)])).bip69 is None
    sorted_outs = fingerprint(mk_tx([(A, 10_000)], [(B, 1_000), (A, 8_000)]))
    unsorted = fingerprint(mk_tx([(A, 10_000)], [(B, 8_000), (A, 1_000)]))
    assert sorted_outs.bip69 is True and unsorted.bip69 is False


def test_signatures_and_pubkeys():
    low = fingerprint(mk_tx([(A, 10_000), (B, 5_000)], [(B, 14_000)],
                            witness=[[der_sig(False), PUB], [der_sig(False), PUB]]))
    assert (low.ecdsa_sigs, low.high_r_sigs, low.low_r_only) == (2, 0, True)
    mixed = fingerprint(mk_tx([(A, 10_000), (B, 5_000)], [(B, 14_000)],
                              witness=[[der_sig(False), PUB], [der_sig(True), UNCOMPRESSED]]))
    assert mixed.low_r_only is False and mixed.uncompressed_pubkey
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)])).low_r_only is None


def test_feerate_integer():
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], fee=1_000)).feerate_int is True  # vsize 250
    assert fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], fee=1_001)).feerate_int is False


def test_signature_ignores_shape_dependent_traits():
    a = fingerprint(mk_tx([(A, 10_000)], [(B, 1_000), (A, 8_000)]))
    b = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)]))
    assert a.bip69 != b.bip69 and a.signature() == b.signature()
    c = fingerprint(mk_tx([(A, 10_000)], [(B, 9_000)], version=1))
    assert c.signature() != b.signature()


def test_real_transaction_fingerprint():
    tx = parse_tx(json.loads((FIX / "tx_c5908e04.json").read_text()))
    fp = fingerprint(tx)
    assert fp.version == 2 and fp.locktime_kind == "zero" and not fp.rbf
    assert "p2pkh" in fp.input_types and fp.ecdsa_sigs >= 1


async def test_heuristic_emits_finding_and_skips_coinbase():
    tx = mk_tx([(A, 10_000)], [(B, 9_000)])
    (f,) = await fingerprint_heuristic(tx, Context())
    assert f.heuristic == "H-FP" and f.label == "fingerprint" and f.evidence["version"] == 2
    assert "signature" in f.evidence
    coinbase = mk_tx([(None, 0)], [(B, 312_500_000)], coinbase=True)
    assert await fingerprint_heuristic(coinbase, Context()) == []
```

`backend/tests/heuristics/test_registry_catalog.py`:
```python
from btcintel.catalog.loader import load_catalog
from btcintel.heuristics.base import registry
from btcintel.paths import catalog_dir


def test_registry_matches_catalog_implemented_heuristics():
    cat = load_catalog(catalog_dir())
    implemented = {
        h.id for h in cat.heuristics
        if h.status == "implemented" and h.parent is None and h.family != "taint"
    }
    assert set(registry()) == implemented
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/heuristics -v`
Expected: FAIL.

- [ ] **Step 2: Implement the framework**

`backend/btcintel/heuristics/__init__.py`: empty.

`backend/btcintel/heuristics/base.py`:
```python
"""Heuristic framework: findings, analysis context, and the detector registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from btcintel.chain.errors import ChainError
from btcintel.chain.models import Outspend, Tx
from btcintel.chain.source import ChainSource


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)

    heuristic: str
    subject: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)


def tx_subject(txid: str) -> str:
    return f"tx:{txid}"


def out_subject(txid: str, n: int) -> str:
    return f"out:{txid}:{n}"


@dataclass
class Context:
    """What a detector may use beyond the transaction itself. No chain = offline analysis."""

    chain: ChainSource | None = None
    coinbase_rules: list[tuple[str, str]] = field(default_factory=list)

    async def outspends(self, txid: str) -> list[Outspend] | None:
        return await self.chain.get_outspends(txid) if self.chain else None

    async def tx(self, txid: str) -> Tx | None:
        return await self.chain.get_tx(txid) if self.chain else None


HeuristicFn = Callable[[Tx, Context], Awaitable[list[Finding]]]
_REGISTRY: dict[str, HeuristicFn] = {}


def heuristic(hid: str) -> Callable[[HeuristicFn], HeuristicFn]:
    def register(fn: HeuristicFn) -> HeuristicFn:
        if hid in _REGISTRY and _REGISTRY[hid] is not fn:
            raise ValueError(f"duplicate heuristic id {hid}")
        _REGISTRY[hid] = fn
        return fn

    return register


def registry() -> dict[str, HeuristicFn]:
    import btcintel.heuristics.all  # noqa: F401  (registers every detector)

    return dict(_REGISTRY)


async def analyze_tx(
    tx: Tx,
    ctx: Context,
    only: Iterable[str] | None = None,
    heuristics: Mapping[str, HeuristicFn] | None = None,
) -> list[Finding]:
    detectors = heuristics if heuristics is not None else registry()
    wanted = set(only) if only is not None else None
    findings: list[Finding] = []
    for hid, fn in detectors.items():
        if wanted is not None and hid not in wanted:
            continue
        try:
            findings.extend(await fn(tx, ctx))
        except ChainError as e:
            findings.append(Finding(heuristic=hid, subject=tx_subject(tx.txid), label="incomplete",
                                    confidence=0.0, evidence={"error": str(e)}))
    return findings
```

- [ ] **Step 3: Implement fingerprinting**

`backend/btcintel/heuristics/fingerprint.py`:
```python
"""H-FP: wallet fingerprinting from transaction fields and construction choices."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from btcintel.chain.models import Tx, TxIn
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject

LOCKTIME_THRESHOLD = 500_000_000
AFS_MAX_DELTA = 2016  # blocks between anti-fee-sniping locktime and inclusion height
FINAL_SEQUENCE = 0xFFFFFFFF
RBF_THRESHOLD = 0xFFFFFFFE  # BIP125: nSequence below this signals replaceability


@dataclass(frozen=True)
class Fingerprint:
    version: int
    locktime: int
    locktime_kind: str
    anti_fee_sniping: bool | None
    rbf: bool
    sequences: tuple[str, ...]
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    bip69: bool | None
    ecdsa_sigs: int
    high_r_sigs: int
    low_r_only: bool | None
    uncompressed_pubkey: bool
    has_op_return: bool
    feerate_int: bool | None

    def signature(self) -> str:
        """Wallet-choice traits used to compare two transactions (H-CHG-FPCONT)."""
        return "|".join([
            f"v{self.version}", f"lt:{self.locktime_kind}", f"rbf:{int(self.rbf)}",
            "in:" + ",".join(self.input_types),
        ])

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "signature": self.signature()}


def _asm_pushes(asm: str) -> list[bytes]:
    tokens = asm.split()
    out = []
    for i, tok in enumerate(tokens[:-1]):
        if tok.startswith("OP_PUSHBYTES_") or tok in ("OP_PUSHDATA1", "OP_PUSHDATA2", "OP_PUSHDATA4"):
            try:
                out.append(bytes.fromhex(tokens[i + 1]))
            except ValueError:
                continue
    return out


def _elements(txin: TxIn) -> list[bytes]:
    elems = []
    for w in txin.witness:
        try:
            elems.append(bytes.fromhex(w))
        except ValueError:
            continue
    return elems + _asm_pushes(txin.scriptsig_asm)


def _is_der_sig(b: bytes) -> bool:
    return len(b) >= 9 and b[0] == 0x30 and b[1] == len(b) - 3 and b[2] == 0x02


def _bip69(tx: Tx) -> bool | None:
    if len(tx.vin) < 2 and len(tx.vout) < 2:
        return None
    ins = [(i.prev_txid, i.prev_vout) for i in tx.vin]
    outs = [(o.value, bytes.fromhex(o.script_hex or "")) for o in tx.vout]
    return ins == sorted(ins) and outs == sorted(outs)


def fingerprint(tx: Tx) -> Fingerprint:
    if tx.locktime == 0:
        kind = "zero"
    elif tx.locktime < LOCKTIME_THRESHOLD:
        kind = "height"
    else:
        kind = "time"
    if not tx.status.confirmed or tx.status.block_height is None:
        afs: bool | None = None
    else:
        delta = tx.status.block_height - tx.locktime
        afs = kind == "height" and 1 <= delta <= AFS_MAX_DELTA
    ecdsa = high_r = 0
    uncompressed = False
    for txin in tx.vin:
        for el in _elements(txin):
            if _is_der_sig(el):
                ecdsa += 1
                high_r += el[3] == 33
            elif len(el) == 65 and el[0] == 0x04:
                uncompressed = True
    return Fingerprint(
        version=tx.version,
        locktime=tx.locktime,
        locktime_kind=kind,
        anti_fee_sniping=afs,
        rbf=any(i.sequence < RBF_THRESHOLD for i in tx.vin),
        sequences=tuple(sorted({f"{i.sequence:08x}" for i in tx.vin})),
        input_types=tuple(sorted({i.script_type or "unknown" for i in tx.vin})),
        output_types=tuple(sorted({o.script_type for o in tx.vout})),
        bip69=_bip69(tx),
        ecdsa_sigs=ecdsa,
        high_r_sigs=high_r,
        low_r_only=(high_r == 0) if ecdsa else None,
        uncompressed_pubkey=uncompressed,
        has_op_return=any(o.script_type == "op_return" for o in tx.vout),
        feerate_int=None if tx.is_coinbase or not tx.vsize else tx.fee % tx.vsize == 0,
    )


@heuristic("H-FP")
async def fingerprint_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    if tx.is_coinbase:
        return []
    return [Finding(heuristic="H-FP", subject=tx_subject(tx.txid), label="fingerprint",
                    confidence=1.0, evidence=fingerprint(tx).as_dict())]
```

`backend/btcintel/heuristics/all.py`:
```python
"""Import every detector module so its @heuristic registrations run."""

from btcintel.heuristics import fingerprint  # noqa: F401
```

- [ ] **Step 4: Flip H-FP in the catalog**

In `catalog/heuristics.yaml`, change the `H-FP` entry:
```yaml
  status: implemented
  implemented_by: btcintel.heuristics.fingerprint.fingerprint_heuristic
```
In `docs/kb/heuristics/h-fp.md`, replace the "Detection in btc-intel" section body with: "Implemented in `backend/btcintel/heuristics/fingerprint.py` (`fingerprint()`), which emits one `H-FP` finding per non-coinbase transaction whose evidence lists every trait above plus a `signature` used by H-CHG-FPCONT." Then regenerate the index:

Run: `cd /home/fancybear/btc-intel/backend && uv run btcintel catalog render`

- [ ] **Step 5: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest -v && uv run ruff check . && uv run btcintel catalog check`
Expected: everything passes, including `test_registry_matches_catalog_implemented_heuristics` ({H-FP}) and `test_generated_docs_up_to_date`.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/heuristics backend/tests/heuristics catalog/heuristics.yaml docs/kb
git commit -m "feat(heuristics): detector framework and wallet fingerprinting (H-FP)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 10: CoinJoin detection (H-CJ + children) and common-input-ownership (H-CIOH)

**Files:**
- Create: `backend/btcintel/heuristics/script.py`, `backend/btcintel/heuristics/coinjoin.py`, `backend/btcintel/heuristics/cioh.py`, `backend/tests/cj_samples.py`
- Modify: `backend/btcintel/heuristics/all.py`; `catalog/heuristics.yaml` (H-CJ, all H-CJ-* children except H-CJ-POST, and H-CIOH → implemented); `docs/kb/heuristics/h-cj*.md`, `docs/kb/heuristics/h-cioh.md`; regenerated `docs/kb/index.md`
- Test: `backend/tests/heuristics/test_script.py`, `backend/tests/heuristics/test_coinjoin.py`, `backend/tests/heuristics/test_cioh.py`

**Interfaces:**
- Consumes: `Tx`, `Finding`, `heuristic`, `tx_subject`, `Context`.
- Produces:
  - `op_return_payloads(tx) -> list[bytes]` (the concatenated pushes of each OP_RETURN output), `is_printable_ascii(data: bytes) -> bool`
  - `WHIRLPOOL_POOLS = (100_000, 1_000_000, 2_500_000, 5_000_000, 25_000_000, 50_000_000)`, `STANDARD_DENOMINATIONS: frozenset[int]`
  - `CoinJoinMatch(kind, heuristic_id, confidence, denomination, anonset, equal_groups)`
  - `classify_coinjoin(tx) -> CoinJoinMatch | None`, where kind ∈ {`whirlpool`, `whirlpool_tx0`, `wasabi2`, `wasabi1`, `joinmarket`, `stonewall`, `generic`}
  - `MULTIPARTY_KINDS` (every kind except `whirlpool_tx0`), `STRONG_KINDS` = {wasabi1, wasabi2, whirlpool, whirlpool_tx0, joinmarket}, `is_multiparty(tx) -> bool`
  - `coinjoin_heuristic`, registered as `H-CJ`, which emits `label="coinjoin:<kind>"`
  - `cioh_addresses(tx) -> list[str] | None`: the distinct input addresses when there are ≥2 and the tx is neither coinbase nor multi-party, otherwise `None`
  - `cioh_heuristic`, registered as `H-CIOH`, which emits `common_input` (0.95) or `cioh_suppressed` (1.0)
  - `tests.cj_samples`: `whirlpool_mix()`, `ashigaru_remix()`, `whirlpool_tx0()`, `thorchain_swap()`, `wasabi2_round(version=1)`, `wasabi1_round()`, `joinmarket_round()`, `stonewall()`, `generic_equal()`

Rules, applied in order (calibrated on 2026-09-25 against crocs-muni ground truth: 57/60 random WabiSabi rounds, and every sampled Whirlpool mix, Tx0 and Wasabi 1 round, were classified correctly; 0 strong false positives across 102 ordinary transactions):

1. **whirlpool:** no OP_RETURN; `n_in == n_out ∈ [5,10]`; every output equals a pool denomination D; every input is in `[D, 1.1·D + 20000]`.
2. **whirlpool_tx0:** exactly one OP_RETURN whose payload is ≥40 bytes and not printable ASCII (real Tx0 payloads are 64 or 81 binary bytes; THORChain memos are ASCII); every spendable output is `v0_p2wpkh`; for some pool D, the outputs in `(D, 1.1·D + 20000]` all share one value.
3. **wasabi2:** `n_in ≥ 5`; all input and output types in {v0_p2wpkh, v1_p2tr}; nVersion 1; nLockTime 0; ≥75% of outputs are standard denominations; at least one equal group.
4. **wasabi1:** largest equal group ≥10, with a value in [7,000,000, 13,000,000] sats; all inputs and outputs P2WPKH.
5. **joinmarket:** largest equal group n ≥ 3; `n_in ≥ n`; `n_out ≤ 2n + 1`; no OP_RETURN.
6. **stonewall:** 4 outputs with exactly one equal pair; `n_in ≥ 2`.
7. **generic:** largest equal group ≥2 and `n_in ≥ 2`.

- [ ] **Step 1: Write the shared samples and failing tests**

`backend/tests/cj_samples.py`:
```python
"""Synthetic CoinJoin-shaped transactions mirroring real mainnet structures (see Task 10 rules)."""

from btcintel.chain.models import Tx
from tests.builders import mk_tx

W = "v0_p2wpkh"
TR = "v1_p2tr"


def _addr(i: int) -> str:
    return f"bc1-sample-{i}"


def whirlpool_mix() -> Tx:
    ins = [(_addr(i), v, W) for i, v in enumerate([1_000_000] * 3 + [1_006_050] * 2)]
    return mk_tx(ins, [(_addr(10 + i), 1_000_000, W) for i in range(5)], version=1)


def ashigaru_remix() -> Tx:
    ins = [(_addr(i), v, W) for i, v in enumerate([2_500_000] * 4 + [2_505_000] * 2)]
    return mk_tx(ins, [(_addr(20 + i), 2_500_000, W) for i in range(6)], version=1)


def whirlpool_tx0(n_inputs: int = 1) -> Tx:
    ins = [(_addr(30 + i), 720_000 // n_inputs, W) for i in range(n_inputs)]
    outs = [(_addr(40), 5_000, W), (_addr(41), 67_648, W)] + [(_addr(42 + i), 106_352, W) for i in range(5)]
    return mk_tx(ins, outs, version=1, op_returns=[bytes(range(64))])


def thorchain_swap() -> Tx:
    memo = b"=:ETH.ETH:0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0"
    return mk_tx([(_addr(50), 500_000, W)], [(_addr(51), 120_000, W), (_addr(52), 370_000, W)],
                 op_returns=[memo])


def wasabi2_round(version: int = 1) -> Tx:
    ins = [(_addr(60 + i), 1_000_000, W if i % 2 else TR) for i in range(12)]
    values = [1_000_000] * 3 + [500_000] * 3 + [200_000] * 2 + [131_072] * 2 + [59_049, 100_000, 4_213_337]
    outs = [(_addr(80 + i), v, W if i % 2 else TR) for i, v in enumerate(values)]
    return mk_tx(ins, outs, version=version, locktime=0)


def wasabi1_round() -> Tx:
    ins = [(_addr(100 + i), 20_000_000, W) for i in range(60)]
    outs = [(_addr(200 + i), 10_987_000, W) for i in range(50)]
    outs += [(_addr(300 + i), 1_000_000 + i * 1_111, W) for i in range(30)]
    return mk_tx(ins, outs, version=1)


def joinmarket_round() -> Tx:
    ins = [(_addr(400 + i), 40_000_000, W) for i in range(11)]
    outs = [(_addr(420 + i), 35_281_835, W) for i in range(5)]
    outs += [(_addr(430 + i), v, W) for i, v in enumerate([12_345_678, 23_456_789, 34_567_890, 45_678_901])]
    return mk_tx(ins, outs, version=2, locktime=846_005, sequence=0xFFFFFFFE)


def stonewall() -> Tx:
    ins = [(_addr(500 + i), 400_000, W) for i in range(3)]
    return mk_tx(ins, [(_addr(510), 50_000, W), (_addr(511), 50_000, W),
                       (_addr(512), 123_456, W), (_addr(513), 654_321, W)])


def generic_equal() -> Tx:
    return mk_tx([(_addr(600), 50_000, W), (_addr(601), 40_000, W)],
                 [(_addr(610), 40_000, W), (_addr(611), 40_000, W), (_addr(612), 777, W)])
```

`backend/tests/heuristics/test_script.py`:
```python
from btcintel.heuristics.script import is_printable_ascii, op_return_payloads
from tests.builders import mk_tx
from btcintel.chain.models import TxOut


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
```

`backend/tests/heuristics/test_coinjoin.py`:
```python
import pytest

from btcintel.heuristics.base import Context
from btcintel.heuristics.coinjoin import (
    MULTIPARTY_KINDS,
    STANDARD_DENOMINATIONS,
    classify_coinjoin,
    coinjoin_heuristic,
    is_multiparty,
)
from tests import cj_samples as s
from tests.builders import mk_tx


@pytest.mark.parametrize("build,kind,denom,anonset", [
    (s.whirlpool_mix, "whirlpool", 1_000_000, 5),
    (s.ashigaru_remix, "whirlpool", 2_500_000, 6),
    (s.whirlpool_tx0, "whirlpool_tx0", 100_000, 5),
    (s.wasabi1_round, "wasabi1", 10_987_000, 50),
    (s.joinmarket_round, "joinmarket", 35_281_835, 5),
    (s.stonewall, "stonewall", 50_000, 2),
    (s.generic_equal, "generic", 40_000, 2),
])
def test_known_structures(build, kind, denom, anonset):
    m = classify_coinjoin(build())
    assert m is not None and (m.kind, m.denomination, m.anonset) == (kind, denom, anonset)
    assert m.heuristic_id.startswith("H-CJ-")


def test_wasabi2_requires_version_1():
    assert classify_coinjoin(s.wasabi2_round(version=1)).kind == "wasabi2"
    assert classify_coinjoin(s.wasabi2_round(version=2)).kind == "generic"


def test_thorchain_swap_is_not_a_tx0():
    assert classify_coinjoin(s.thorchain_swap()) is None


def test_ordinary_transactions():
    assert classify_coinjoin(mk_tx([("a", 100_000)], [("b", 60_000), ("c", 39_000)])) is None
    assert classify_coinjoin(mk_tx([("a", 50_000), ("b", 60_000)], [("c", 70_000), ("d", 39_000)])) is None
    assert classify_coinjoin(mk_tx([(None, 0)], [("m", 312_500_000)], coinbase=True)) is None


def test_multiparty_excludes_tx0():
    assert "whirlpool_tx0" not in MULTIPARTY_KINDS
    assert is_multiparty(s.whirlpool_mix()) and not is_multiparty(s.whirlpool_tx0())


def test_standard_denominations():
    assert {5_000, 6_561, 13_122, 131_072, 200_000, 1_000_000} <= STANDARD_DENOMINATIONS
    assert 4_999 not in STANDARD_DENOMINATIONS and 1_024 not in STANDARD_DENOMINATIONS


async def test_heuristic_finding():
    (f,) = await coinjoin_heuristic(s.whirlpool_mix(), Context())
    assert f.heuristic == "H-CJ" and f.label == "coinjoin:whirlpool" and f.evidence["multiparty"]
    assert await coinjoin_heuristic(mk_tx([("a", 1000)], [("b", 900)]), Context()) == []
```

`backend/tests/heuristics/test_cioh.py`:
```python
from btcintel.heuristics.base import Context
from btcintel.heuristics.cioh import cioh_addresses, cioh_heuristic
from tests import cj_samples as s
from tests.builders import mk_tx


async def test_ordinary_multi_input_links_addresses():
    tx = mk_tx([("a", 50_000), ("b", 60_000), ("a", 1_000)], [("c", 100_000)])
    assert cioh_addresses(tx) == ["a", "b"]
    (f,) = await cioh_heuristic(tx, Context())
    assert (f.label, f.evidence["addresses"]) == ("common_input", ["a", "b"])


async def test_coinjoin_suppresses_cioh():
    tx = s.whirlpool_mix()
    assert cioh_addresses(tx) is None
    (f,) = await cioh_heuristic(tx, Context())
    assert f.label == "cioh_suppressed" and f.evidence["reason"] == "coinjoin:whirlpool"


async def test_tx0_keeps_cioh():
    assert cioh_addresses(s.whirlpool_tx0(n_inputs=2)) is not None


async def test_single_address_and_coinbase():
    assert cioh_addresses(mk_tx([("a", 1), ("a", 2)], [("b", 2)])) is None
    assert await cioh_heuristic(mk_tx([("a", 1)], [("b", 1)]), Context()) == []
    assert await cioh_heuristic(mk_tx([(None, 0)], [("m", 1)], coinbase=True), Context()) == []
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/heuristics -v`
Expected: FAIL (modules missing).

- [ ] **Step 2: Implement**

`backend/btcintel/heuristics/script.py`:
```python
"""Script helpers shared by detectors."""

from __future__ import annotations

from btcintel.chain.models import Tx


def op_return_payloads(tx: Tx) -> list[bytes]:
    """Concatenated data pushes of each OP_RETURN output (malformed scripts yield partial data)."""
    payloads = []
    for out in tx.vout:
        if out.script_type != "op_return":
            continue
        try:
            script = bytes.fromhex(out.script_hex)
        except ValueError:
            continue
        if not script or script[0] != 0x6A:
            continue
        data = bytearray()
        i = 1
        while i < len(script):
            op = script[i]
            i += 1
            if 0x01 <= op <= 0x4B:
                n = op
            elif op == 0x4C:
                if i >= len(script):
                    break
                n = script[i]
                i += 1
            elif op == 0x4D:
                if i + 2 > len(script):
                    break
                n = int.from_bytes(script[i : i + 2], "little")
                i += 2
            else:
                continue
            data += script[i : i + n]
            i += n
        payloads.append(bytes(data))
    return payloads


def is_printable_ascii(data: bytes) -> bool:
    return bool(data) and all(0x20 <= b < 0x7F for b in data)
```

`backend/btcintel/heuristics/coinjoin.py`:
```python
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
    if anonset >= 3 and n_in >= anonset and n_out <= 2 * anonset + 1 and n_opret == 0:
        return match("joinmarket", denom, anonset)
    if n_out == 4 and anonset == 2 and groups == 1 and n_in >= 2:
        return match("stonewall", denom, anonset)
    if anonset >= 2 and n_in >= 2:
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
```

`backend/btcintel/heuristics/cioh.py`:
```python
"""H-CIOH: common-input-ownership, suppressed for multi-party (CoinJoin/Stonewall) transactions."""

from __future__ import annotations

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, classify_coinjoin


def cioh_addresses(tx: Tx) -> list[str] | None:
    if tx.is_coinbase:
        return None
    m = classify_coinjoin(tx)
    if m is not None and m.kind in MULTIPARTY_KINDS:
        return None
    addresses = tx.input_addresses()
    return addresses if len(addresses) >= 2 else None


@heuristic("H-CIOH")
async def cioh_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    if tx.is_coinbase:
        return []
    addresses = tx.input_addresses()
    if len(addresses) < 2:
        return []
    m = classify_coinjoin(tx)
    if m is not None and m.kind in MULTIPARTY_KINDS:
        return [Finding(heuristic="H-CIOH", subject=tx_subject(tx.txid), label="cioh_suppressed",
                        confidence=1.0,
                        evidence={"reason": f"coinjoin:{m.kind}", "input_addresses": len(addresses)})]
    return [Finding(heuristic="H-CIOH", subject=tx_subject(tx.txid), label="common_input",
                    confidence=0.95, evidence={"addresses": addresses})]
```

Update `backend/btcintel/heuristics/all.py`:
```python
"""Import every detector module so its @heuristic registrations run."""

from btcintel.heuristics import cioh, coinjoin, fingerprint  # noqa: F401
```

- [ ] **Step 3: Flip the catalog entries and update the KB pages**

In `catalog/heuristics.yaml` set `status: implemented` and:
- `H-CJ` → `implemented_by: btcintel.heuristics.coinjoin.coinjoin_heuristic`
- `H-CJ-WASABI1`, `H-CJ-WASABI2`, `H-CJ-WHIRLPOOL`, `H-CJ-WHIRLPOOL-TX0`, `H-CJ-JOINMARKET`, `H-CJ-STONEWALL`, `H-CJ-GENERIC` → `implemented_by: btcintel.heuristics.coinjoin.classify_coinjoin`
- `H-CIOH` → `implemented_by: btcintel.heuristics.cioh.cioh_heuristic`

Update each page's "Detection in btc-intel" section with the implemented rule (copy the numbered rule above for its kind) and the calibration note. Then run `uv run btcintel catalog render`.

- [ ] **Step 4: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest -v && uv run ruff check . && uv run btcintel catalog check`
Expected: all pass. The registry now holds {H-FP, H-CJ, H-CIOH}.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/heuristics backend/tests/cj_samples.py backend/tests/heuristics catalog/heuristics.yaml docs/kb
git commit -m "feat(heuristics): CoinJoin detection (Whirlpool, WabiSabi, ZeroLink, JoinMarket, Stonewall) and CIOH

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Change-output detection (H-CHG + signals)

**Files:**
- Create: `backend/btcintel/heuristics/change.py`
- Modify: `backend/btcintel/heuristics/all.py`; `catalog/heuristics.yaml` (H-CHG, H-CHG-SELF, H-CHG-SCRIPT, H-CHG-ROUND, H-CHG-UNNECESSARY, H-CHG-FPCONT → implemented); the matching KB pages; regenerated index
- Test: `backend/tests/heuristics/test_change.py`

**Interfaces:**
- Consumes: `classify_coinjoin`, `MULTIPARTY_KINDS`, `fingerprint`, `Context`, `FakeChain` (tests).
- Produces:
  - `Vote(signal: str, output: int, weight: float, detail: str)`
  - `ChangeResult(applicable: bool, change_output: int | None, probabilities: dict[int, float], votes: tuple[Vote, ...], reason: str = "")`
  - `WEIGHTS`, `MIN_PROBABILITY = 0.6`, `MAX_OUTPUTS = 4`, `trailing_zeros(value) -> int`
  - `applicability(tx) -> str | None`: `None` when applicable, otherwise the reason
  - `offline_votes(tx) -> list[Vote]`, `async fingerprint_votes(tx, ctx) -> list[Vote]`, `combine(outputs, votes) -> tuple[int | None, dict[int, float]]`
  - `async detect_change(tx, ctx=None) -> ChangeResult`, `detect_change_offline(tx) -> ChangeResult`
  - `remainder_output(tx) -> int | None`: the change output if detected, otherwise the largest spendable output (used by peel following)
  - `change_heuristic`, registered as `H-CHG`

Signals and weights (log-odds added per output; probability = sigmoid(sum); change = the unique argmax with p ≥ 0.6):

| Signal | Vote |
|---|---|
| H-CHG-SELF | +4.0 to an output paying an input address |
| H-CHG-SCRIPT | +1.0 to the only output matching the inputs' single script type; −0.5 to the others |
| H-CHG-ROUND | +1.2 to the only ragged output (≤3 trailing decimal zeros) when every other output is round (≥5 zeros); −1.2 to each round output |
| H-CHG-UNNECESSARY | +1.0 to the only output smaller than the smallest input, when there are ≥2 inputs |
| H-CHG-FPCONT | needs a chain: +1.0 when the output's spending tx has the same fingerprint signature, −0.3 otherwise |

Not applicable when the tx is coinbase, is a multi-party CoinJoin, or has <2 or >4 spendable outputs (checked in that order).

- [ ] **Step 1: Write the failing tests**

`backend/tests/heuristics/test_change.py`:
```python
import pytest

from btcintel.heuristics.base import Context
from btcintel.heuristics.change import (
    change_heuristic,
    detect_change,
    detect_change_offline,
    remainder_output,
    trailing_zeros,
)
from tests import cj_samples as s
from tests.builders import mk_tx
from tests.fakes import FakeChain


def votes_by_signal(result):
    return {(v.signal, v.output) for v in result.votes}


async def test_self_change():
    tx = mk_tx([("a", 100_000)], [("b", 30_000), ("a", 69_000)])
    r = await detect_change(tx)
    assert r.applicable and r.change_output == 1 and ("H-CHG-SELF", 1) in votes_by_signal(r)
    assert r.probabilities[1] == pytest.approx(0.982, abs=1e-3)


async def test_script_type_and_round_agree():
    tx = mk_tx([("a", 1_000_000, "p2pkh")], [("b", 400_000, "v0_p2wpkh"), ("c", 599_000, "p2pkh")])
    r = await detect_change(tx)
    assert r.change_output == 1
    assert {("H-CHG-SCRIPT", 1), ("H-CHG-SCRIPT", 0), ("H-CHG-ROUND", 1), ("H-CHG-ROUND", 0)} <= votes_by_signal(r)
    assert r.probabilities[1] == pytest.approx(0.9002, abs=1e-3)


async def test_round_payment_only():
    r = await detect_change(mk_tx([("a", 250_000)], [("b", 100_000), ("c", 149_000)]))
    assert r.change_output == 1 and r.probabilities[1] == pytest.approx(0.7685, abs=1e-3)


async def test_unnecessary_input():
    r = await detect_change(mk_tx([("a", 50_000), ("b", 60_000)], [("c", 95_000), ("d", 14_000)]))
    assert r.change_output == 1 and ("H-CHG-UNNECESSARY", 1) in votes_by_signal(r)


async def test_no_signal_means_undetermined():
    r = await detect_change(mk_tx([("a", 800_000)], [("b", 123_456), ("c", 654_321)]))
    assert r.applicable and r.change_output is None and r.probabilities == {0: 0.5, 1: 0.5}


@pytest.mark.parametrize("tx,reason", [
    (s.whirlpool_mix(), "coinjoin:whirlpool"),
    (mk_tx([("a", 10_000)], [(f"o{i}", 1_000) for i in range(6)]), "more than 4 outputs (batch payment)"),
    (mk_tx([("a", 10_000)], [("b", 9_000)]), "fewer than two outputs"),
    (mk_tx([(None, 0)], [("m", 1), ("n", 2)], coinbase=True), "coinbase"),
])
async def test_not_applicable(tx, reason):
    r = await detect_change(tx)
    assert not r.applicable and r.reason == reason and r.change_output is None


async def test_fingerprint_continuity_uses_spending_transactions():
    t = mk_tx([("a", 1_000_000)], [("b", 123_456), ("c", 654_321)])
    other_wallet = mk_tx([(t, 0)], [("x", 120_000)], version=1)
    same_wallet = mk_tx([(t, 1)], [("y", 650_000)])
    r = await detect_change(t, Context(chain=FakeChain([t, other_wallet, same_wallet])))
    assert r.change_output == 1
    assert ("H-CHG-FPCONT", 1) in votes_by_signal(r) and ("H-CHG-FPCONT", 0) in votes_by_signal(r)


async def test_offline_matches_async_without_chain():
    tx = mk_tx([("a", 250_000)], [("b", 100_000), ("c", 149_000)])
    assert detect_change_offline(tx) == await detect_change(tx)


def test_remainder_output_falls_back_to_largest():
    assert remainder_output(mk_tx([("a", 800_000)], [("b", 123_456), ("c", 654_321)])) == 1
    assert remainder_output(mk_tx([("a", 100_000)], [("a", 90_000), ("b", 9_000)])) == 0


def test_trailing_zeros():
    assert [trailing_zeros(v) for v in (0, 7, 1_000_000, 149_000)] == [0, 0, 6, 3]


async def test_heuristic_finding():
    tx = mk_tx([("a", 100_000)], [("b", 30_000), ("a", 69_000)])
    (f,) = await change_heuristic(tx, Context())
    assert f.heuristic == "H-CHG" and f.subject == f"out:{tx.txid}:1" and f.label == "change"
    assert f.evidence["votes"][0]["signal"] == "H-CHG-SELF"
    assert await change_heuristic(mk_tx([("a", 800_000)], [("b", 123_456), ("c", 654_321)]), Context()) == []
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/heuristics/test_change.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/heuristics/change.py`:
```python
"""H-CHG: change-output detection as a weighted log-odds vote over independent signals."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from btcintel.chain.models import Tx, TxOut
from btcintel.heuristics.base import Context, Finding, heuristic, out_subject
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, classify_coinjoin
from btcintel.heuristics.fingerprint import fingerprint

WEIGHTS = {
    "H-CHG-SELF": 4.0, "H-CHG-SCRIPT": 1.0, "H-CHG-ROUND": 1.2, "H-CHG-UNNECESSARY": 1.0,
    "H-CHG-FPCONT": 1.0,
}
MIN_PROBABILITY = 0.6
MAX_OUTPUTS = 4


@dataclass(frozen=True)
class Vote:
    signal: str
    output: int
    weight: float
    detail: str


@dataclass(frozen=True)
class ChangeResult:
    applicable: bool
    change_output: int | None
    probabilities: dict[int, float]
    votes: tuple[Vote, ...]
    reason: str = ""


def trailing_zeros(value: int) -> int:
    if value <= 0:
        return 0
    n = 0
    while value % 10 == 0:
        value //= 10
        n += 1
    return n


def applicability(tx: Tx) -> str | None:
    if tx.is_coinbase:
        return "coinbase"
    m = classify_coinjoin(tx)
    if m is not None and m.kind in MULTIPARTY_KINDS:
        return f"coinjoin:{m.kind}"
    outs = tx.spendable_outputs()
    if len(outs) < 2:
        return "fewer than two outputs"
    if len(outs) > MAX_OUTPUTS:
        return f"more than {MAX_OUTPUTS} outputs (batch payment)"
    return None


def offline_votes(tx: Tx) -> list[Vote]:
    outs = tx.spendable_outputs()
    votes: list[Vote] = []
    inputs = set(tx.input_addresses())
    for o in outs:
        if o.address and o.address in inputs:
            votes.append(Vote("H-CHG-SELF", o.n, WEIGHTS["H-CHG-SELF"], "pays back to an input address"))
    in_types = {i.script_type for i in tx.vin}
    if len(in_types) == 1:
        (itype,) = in_types
        same = [o for o in outs if o.script_type == itype]
        if len(same) == 1:
            w = WEIGHTS["H-CHG-SCRIPT"]
            votes.append(Vote("H-CHG-SCRIPT", same[0].n, w, f"only output with the inputs' script type {itype}"))
            votes += [Vote("H-CHG-SCRIPT", o.n, -0.5 * w, f"script type {o.script_type} differs from inputs")
                      for o in outs if o is not same[0]]
    round_outs = [o for o in outs if trailing_zeros(o.value) >= 5]
    ragged = [o for o in outs if trailing_zeros(o.value) <= 3]
    if len(ragged) == 1 and len(round_outs) == len(outs) - 1:
        w = WEIGHTS["H-CHG-ROUND"]
        votes.append(Vote("H-CHG-ROUND", ragged[0].n, w, "only non-round output"))
        votes += [Vote("H-CHG-ROUND", o.n, -w, f"round amount {o.value} sats looks like a payment")
                  for o in round_outs]
    if len(tx.vin) >= 2:
        smallest = min(i.value for i in tx.vin)
        below = [o for o in outs if o.value < smallest]
        if len(below) == 1:
            votes.append(Vote("H-CHG-UNNECESSARY", below[0].n, WEIGHTS["H-CHG-UNNECESSARY"],
                              f"smaller than the smallest input ({smallest} sats)"))
    return votes


async def fingerprint_votes(tx: Tx, ctx: Context) -> list[Vote]:
    spends = await ctx.outspends(tx.txid)
    if not spends:
        return []
    mine = fingerprint(tx).signature()
    w = WEIGHTS["H-CHG-FPCONT"]
    votes = []
    for o in tx.spendable_outputs():
        sp = spends[o.n] if o.n < len(spends) else None
        if sp is None or not sp.spent or not sp.txid:
            continue
        child = await ctx.tx(sp.txid)
        if child is None:
            continue
        if fingerprint(child).signature() == mine:
            votes.append(Vote("H-CHG-FPCONT", o.n, w, "spent by a transaction with the same wallet fingerprint"))
        else:
            votes.append(Vote("H-CHG-FPCONT", o.n, -0.3 * w,
                              "spent by a transaction with a different wallet fingerprint"))
    return votes


def combine(outputs: Sequence[TxOut], votes: Sequence[Vote]) -> tuple[int | None, dict[int, float]]:
    score = {o.n: 0.0 for o in outputs}
    for v in votes:
        score[v.output] += v.weight
    probs = {n: round(1 / (1 + math.exp(-s)), 4) for n, s in score.items()}
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    best, p = ranked[0]
    if p >= MIN_PROBABILITY and p > ranked[1][1]:
        return best, probs
    return None, probs


def _not_applicable(reason: str) -> ChangeResult:
    return ChangeResult(False, None, {}, (), reason)


def detect_change_offline(tx: Tx) -> ChangeResult:
    reason = applicability(tx)
    if reason:
        return _not_applicable(reason)
    votes = offline_votes(tx)
    change, probs = combine(tx.spendable_outputs(), votes)
    return ChangeResult(True, change, probs, tuple(votes))


async def detect_change(tx: Tx, ctx: Context | None = None) -> ChangeResult:
    reason = applicability(tx)
    if reason:
        return _not_applicable(reason)
    votes = offline_votes(tx)
    if ctx is not None and ctx.chain is not None:
        votes += await fingerprint_votes(tx, ctx)
    change, probs = combine(tx.spendable_outputs(), votes)
    return ChangeResult(True, change, probs, tuple(votes))


def remainder_output(tx: Tx) -> int | None:
    result = detect_change_offline(tx)
    if result.change_output is not None:
        return result.change_output
    outs = tx.spendable_outputs()
    return max(outs, key=lambda o: o.value).n if outs else None


@heuristic("H-CHG")
async def change_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    r = await detect_change(tx, ctx)
    if r.change_output is None:
        return []
    return [Finding(
        heuristic="H-CHG", subject=out_subject(tx.txid, r.change_output), label="change",
        confidence=r.probabilities[r.change_output],
        evidence={"votes": [asdict(v) for v in r.votes],
                  "probabilities": {str(k): v for k, v in r.probabilities.items()}},
    )]
```

Update `all.py`: `from btcintel.heuristics import change, cioh, coinjoin, fingerprint  # noqa: F401`

- [ ] **Step 3: Flip the catalog entries and update the KB pages**

Set `status: implemented` and:
- `H-CHG` → `implemented_by: btcintel.heuristics.change.change_heuristic`
- `H-CHG-SELF`, `H-CHG-SCRIPT`, `H-CHG-ROUND`, `H-CHG-UNNECESSARY` → `implemented_by: btcintel.heuristics.change.offline_votes`
- `H-CHG-FPCONT` → `implemented_by: btcintel.heuristics.change.fingerprint_votes`

Leave `H-CHG-FRESH` and `H-CHG-POSITION` as `planned`. Update the KB pages' "Detection in btc-intel" sections with the weights table above, then run `uv run btcintel catalog render`.

- [ ] **Step 4: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest -v && uv run ruff check . && uv run btcintel catalog check`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/heuristics backend/tests/heuristics/test_change.py catalog/heuristics.yaml docs/kb
git commit -m "feat(heuristics): change-output detection by weighted signal voting (H-CHG)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Motifs (H-PEEL, H-MOTIF-FANOUT/FANIN), cross-chain markers (H-XCHAIN), miner attribution (H-COINBASE), flags

**Files:**
- Create: `backend/btcintel/heuristics/patterns.py`, `backend/btcintel/heuristics/crosschain.py`, `backend/btcintel/heuristics/coinbase.py`, `backend/btcintel/heuristics/flags.py`
- Modify: `backend/btcintel/heuristics/all.py`; `catalog/heuristics.yaml` (H-PEEL, H-MOTIF-FANOUT, H-MOTIF-FANIN, H-XCHAIN, H-COINBASE → implemented); KB pages; regenerated index
- Test: `backend/tests/heuristics/test_patterns.py`, `backend/tests/heuristics/test_crosschain.py`, `backend/tests/heuristics/test_coinbase.py`, `backend/tests/heuristics/test_flags.py`

**Interfaces:**
- Consumes: `is_multiparty`, `classify_coinjoin`, `op_return_payloads`, `is_printable_ascii`.
- Produces:
  - `peel_shape(tx) -> dict | None`, with keys `remainder_output`, `peel_output`, `peel_value`, `remainder_share`
  - `fanout_shape(tx) -> dict | None`, with keys `label` (`"dispersal_uniform"` or `"fan_out"`), `n_out`, `cv`
  - `fanin_shape(tx) -> dict | None`, with keys `n_in`, `distinct_input_addresses`
  - `peel_heuristic` (`H-PEEL`), `fanout_heuristic` (`H-MOTIF-FANOUT`), `fanin_heuristic` (`H-MOTIF-FANIN`)
  - `ThorMemo(action, asset, destination, inbound_hash, memo)`, where action ∈ {swap, add, withdraw, donate, outbound, refund}
  - `parse_thorchain_memo(text) -> ThorMemo | None`, `xchain_markers(tx) -> list[tuple[str, float, dict]]`, `crosschain_heuristic` (`H-XCHAIN`)
  - `coinbase_text(tx) -> str`, `match_pool(scriptsig_hex, rules) -> str | None`, `coinbase_heuristic` (`H-COINBASE`), which uses `ctx.coinbase_rules`
  - `tx_flags(tx) -> list[str]`: offline labels such as `coinbase`, `coinjoin:<kind>`, `peel_step`, `dispersal_uniform`, `fan_out`, `consolidation`, `omni_layer`, `thorchain:<action>`

THORChain memo grammar (dev.thorchain.org, verified 2026-09-25):
- `SWAP:ASSET:DEST[:LIM…]`, with aliases `s`, `=`, `=<`
- `ADD:POOL[:PAIRED]`, with aliases `a`, `+`
- `WITHDRAW:POOL:BPS`, with aliases `wd`, `-`
- `DONATE:POOL`, with alias `d`
- the outbound memos `OUT:<inbound hash>` and `REFUND:<inbound hash>`

An asset must look like `CHAIN.ASSET`, `CHAIN~ASSET` or `CHAIN/ASSET`, which rejects arbitrary text.

- [ ] **Step 1: Write the failing tests**

`backend/tests/heuristics/test_patterns.py`:
```python
from btcintel.heuristics.base import Context
from btcintel.heuristics.patterns import (
    fanin_heuristic,
    fanin_shape,
    fanout_heuristic,
    fanout_shape,
    peel_heuristic,
    peel_shape,
)
from tests import cj_samples as s
from tests.builders import mk_tx


async def test_peel_step():
    tx = mk_tx([("a", 10_000_000)], [("b", 500_000), ("c", 9_490_000)])
    assert peel_shape(tx) == {"remainder_output": 1, "peel_output": 0, "peel_value": 500_000,
                              "remainder_share": 0.95}
    (f,) = await peel_heuristic(tx, Context())
    assert f.label == "peel_step"
    assert peel_shape(mk_tx([("a", 10_000_000)], [("b", 5_000_000), ("c", 4_990_000)])) is None
    assert peel_shape(mk_tx([("a", 10_000_000)], [("b", 1), ("c", 2), ("d", 9_000_000)])) is None


async def test_fanout_uniform_vs_varied():
    uniform = mk_tx([("a", 2_000_000)], [(f"o{i}", 100_000) for i in range(12)])
    varied = mk_tx([("a", 9_000_000)], [(f"o{i}", 10_000 * (i + 1) ** 2) for i in range(12)])
    assert fanout_shape(uniform)["label"] == "dispersal_uniform"
    assert fanout_shape(varied)["label"] == "fan_out"
    assert fanout_shape(mk_tx([("a", 9_000)], [(f"o{i}", 1_000) for i in range(5)])) is None
    (f,) = await fanout_heuristic(uniform, Context())
    assert f.heuristic == "H-MOTIF-FANOUT" and f.confidence == 0.6


async def test_fanin_consolidation_excludes_coinjoin():
    tx = mk_tx([(f"i{i}", 10_000) for i in range(12)], [("z", 110_000)])
    assert fanin_shape(tx) == {"n_in": 12, "distinct_input_addresses": 12}
    (f,) = await fanin_heuristic(tx, Context())
    assert f.label == "consolidation"
    assert fanin_shape(s.wasabi1_round()) is None
```

`backend/tests/heuristics/test_crosschain.py`:
```python
import pytest

from btcintel.heuristics.base import Context
from btcintel.heuristics.crosschain import crosschain_heuristic, parse_thorchain_memo, xchain_markers
from tests import cj_samples as s
from tests.builders import mk_tx

H = "a" * 64


@pytest.mark.parametrize("memo,action,asset,dest,inbound", [
    ("=:ETH.ETH:0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0", "swap", "ETH.ETH",
     "0xe6a30f4f3bad978910e2cbb4d97581f5b5a0ade0", None),
    ("SWAP:BTC.BTC:bc1qxyz:0/1/0", "swap", "BTC.BTC", "bc1qxyz", None),
    ("s:eth.usdt-0xdac17f958d2ee523a2206206994597c13d831ec7:0xabc", "swap",
     "ETH.USDT-0XDAC17F958D2EE523A2206206994597C13D831EC7", "0xabc", None),
    ("+:BTC.BTC", "add", "BTC.BTC", None, None),
    ("WITHDRAW:BTC/BTC:10000", "withdraw", "BTC/BTC", None, None),
    ("d:ETH.ETH", "donate", "ETH.ETH", None, None),
    (f"OUT:{H}", "outbound", None, None, H),
    (f"REFUND:{H}", "refund", None, None, H),
])
def test_memo_grammar(memo, action, asset, dest, inbound):
    m = parse_thorchain_memo(memo)
    assert (m.action, m.asset, m.destination, m.inbound_hash) == (action, asset, dest, inbound)


@pytest.mark.parametrize("text", ["hello world", "=:notanasset:addr", "OUT:xyz", "", "SWAP"])
def test_non_memos(text):
    assert parse_thorchain_memo(text) is None


async def test_heuristic_on_thorchain_and_omni():
    (f,) = await crosschain_heuristic(s.thorchain_swap(), Context())
    assert f.label == "thorchain:swap" and f.evidence["destination"].startswith("0xe6a3")
    omni = mk_tx([("a", 10_000)], [("b", 546)], op_returns=[b"omni" + bytes(16)])
    assert [m[0] for m in xchain_markers(omni)] == ["omni_layer"]
    assert xchain_markers(s.whirlpool_tx0()) == []
```

`backend/tests/heuristics/test_coinbase.py`:
```python
import json
from pathlib import Path

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.base import Context
from btcintel.heuristics.coinbase import coinbase_heuristic, match_pool
from tests.builders import mk_tx

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"
COINBASE = parse_tx(json.loads((FIX / "tx_coinbase_900000.json").read_text()))


async def test_known_pool():
    (f,) = await coinbase_heuristic(COINBASE, Context(coinbase_rules=[("/ViaBTC/", "ViaBTC")]))
    assert f.label == "miner:ViaBTC" and f.evidence["pool"] == "ViaBTC"


async def test_unknown_pool_keeps_text():
    (f,) = await coinbase_heuristic(COINBASE, Context())
    assert f.label == "miner:unknown" and "ViaBTC" in f.evidence["coinbase_text"]


async def test_non_coinbase_ignored():
    assert await coinbase_heuristic(mk_tx([("a", 1)], [("b", 1)]), Context()) == []


def test_match_pool_uses_rule_order():
    hexed = b"xx/F2Pool/xyz/yy".hex()
    assert match_pool(hexed, [("/F2Pool/xyz/", "Other"), ("/F2Pool/", "F2Pool")]) == "Other"
    assert match_pool(hexed, []) is None
```

`backend/tests/heuristics/test_flags.py`:
```python
import json
from pathlib import Path

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.flags import tx_flags
from tests import cj_samples as s
from tests.builders import mk_tx

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "esplora"


def test_flags():
    assert tx_flags(s.whirlpool_mix()) == ["coinjoin:whirlpool"]
    assert tx_flags(mk_tx([("a", 10_000_000)], [("b", 500_000), ("c", 9_490_000)])) == ["peel_step"]
    assert "thorchain:swap" in tx_flags(s.thorchain_swap())
    assert tx_flags(parse_tx(json.loads((FIX / "tx_coinbase_900000.json").read_text()))) == ["coinbase"]
    assert tx_flags(mk_tx([("a", 800_000)], [("b", 400_000), ("c", 399_000)])) == []
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/heuristics -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/heuristics/patterns.py`:
```python
"""H-PEEL, H-MOTIF-FANOUT, H-MOTIF-FANIN: structural motifs of a single transaction."""

from __future__ import annotations

import statistics
from typing import Any

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject
from btcintel.heuristics.coinjoin import is_multiparty

PEEL_REMAINDER_SHARE = 0.75
FANOUT_MIN_OUTPUTS = 10
FANOUT_MAX_INPUTS = 3
UNIFORM_CV = 0.2
FANIN_MIN_INPUTS = 10
FANIN_MAX_OUTPUTS = 2


def peel_shape(tx: Tx) -> dict[str, Any] | None:
    outs = tx.spendable_outputs()
    if tx.is_coinbase or not 1 <= len(tx.vin) <= 2 or len(outs) != 2:
        return None
    total = sum(o.value for o in outs)
    big, small = sorted(outs, key=lambda o: o.value, reverse=True)
    if total <= 0 or big.value < PEEL_REMAINDER_SHARE * total:
        return None
    return {"remainder_output": big.n, "peel_output": small.n, "peel_value": small.value,
            "remainder_share": round(big.value / total, 3)}


def fanout_shape(tx: Tx) -> dict[str, Any] | None:
    outs = tx.spendable_outputs()
    if tx.is_coinbase or len(outs) < FANOUT_MIN_OUTPUTS or len(tx.vin) > FANOUT_MAX_INPUTS:
        return None
    if is_multiparty(tx):
        return None
    values = [o.value for o in outs]
    mean = statistics.fmean(values)
    cv = statistics.pstdev(values) / mean if mean else 0.0
    return {"label": "dispersal_uniform" if cv < UNIFORM_CV else "fan_out", "n_out": len(outs),
            "cv": round(cv, 3)}


def fanin_shape(tx: Tx) -> dict[str, Any] | None:
    if tx.is_coinbase or len(tx.vin) < FANIN_MIN_INPUTS:
        return None
    if len(tx.spendable_outputs()) > FANIN_MAX_OUTPUTS or is_multiparty(tx):
        return None
    return {"n_in": len(tx.vin), "distinct_input_addresses": len(tx.input_addresses())}


@heuristic("H-PEEL")
async def peel_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    shape = peel_shape(tx)
    if shape is None:
        return []
    return [Finding(heuristic="H-PEEL", subject=tx_subject(tx.txid), label="peel_step",
                    confidence=0.5, evidence=shape)]


@heuristic("H-MOTIF-FANOUT")
async def fanout_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    shape = fanout_shape(tx)
    if shape is None:
        return []
    confidence = 0.6 if shape["label"] == "dispersal_uniform" else 0.5
    return [Finding(heuristic="H-MOTIF-FANOUT", subject=tx_subject(tx.txid), label=shape["label"],
                    confidence=confidence, evidence=shape)]


@heuristic("H-MOTIF-FANIN")
async def fanin_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    shape = fanin_shape(tx)
    if shape is None:
        return []
    return [Finding(heuristic="H-MOTIF-FANIN", subject=tx_subject(tx.txid), label="consolidation",
                    confidence=0.6, evidence=shape)]
```

`backend/btcintel/heuristics/crosschain.py`:
```python
"""H-XCHAIN: cross-chain exit markers in OP_RETURN data (THORChain memos, Omni Layer)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject
from btcintel.heuristics.script import is_printable_ascii, op_return_payloads

_SWAP = {"SWAP", "S", "=", "=<"}
_ADD = {"ADD", "A", "+"}
_WITHDRAW = {"WITHDRAW", "WD", "-"}
_DONATE = {"DONATE", "D"}
_ASSET = re.compile(r"^[A-Za-z0-9]+[.~/][A-Za-z0-9._\-]+$")
_HASH = re.compile(r"^[0-9A-Fa-f]{64}$")


@dataclass(frozen=True)
class ThorMemo:
    action: str
    asset: str | None
    destination: str | None
    inbound_hash: str | None
    memo: str


def parse_thorchain_memo(text: str) -> ThorMemo | None:
    memo = text.strip()
    parts = memo.split(":")
    fn = parts[0].upper()

    def arg(k: int) -> str | None:
        return parts[k].strip() if len(parts) > k and parts[k].strip() else None

    if fn in ("OUT", "REFUND"):
        h = arg(1)
        if h is None or not _HASH.match(h):
            return None
        return ThorMemo("outbound" if fn == "OUT" else "refund", None, None, h, memo)
    asset = arg(1)
    if asset is None or not _ASSET.match(asset):
        return None
    if fn in _SWAP:
        return ThorMemo("swap", asset.upper(), arg(2), None, memo)
    if fn in _ADD:
        return ThorMemo("add", asset.upper(), arg(2), None, memo)
    if fn in _WITHDRAW:
        return ThorMemo("withdraw", asset.upper(), None, None, memo)
    if fn in _DONATE:
        return ThorMemo("donate", asset.upper(), None, None, memo)
    return None


def xchain_markers(tx: Tx) -> list[tuple[str, float, dict[str, Any]]]:
    markers = []
    for payload in op_return_payloads(tx):
        if payload.startswith(b"omni"):
            markers.append(("omni_layer", 0.95, {"payload_hex": payload.hex()}))
            continue
        if not is_printable_ascii(payload):
            continue
        memo = parse_thorchain_memo(payload.decode("ascii"))
        if memo is not None:
            markers.append((f"thorchain:{memo.action}", 0.9, asdict(memo)))
    return markers


@heuristic("H-XCHAIN")
async def crosschain_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    return [Finding(heuristic="H-XCHAIN", subject=tx_subject(tx.txid), label=label,
                    confidence=confidence, evidence=evidence)
            for label, confidence, evidence in xchain_markers(tx)]
```

`backend/btcintel/heuristics/coinbase.py`:
```python
"""H-COINBASE: attribute newly mined coins to pools via coinbase scriptSig tags."""

from __future__ import annotations

from collections.abc import Sequence

from btcintel.chain.models import Tx
from btcintel.heuristics.base import Context, Finding, heuristic, tx_subject


def _decode(scriptsig_hex: str) -> str:
    try:
        return bytes.fromhex(scriptsig_hex).decode("latin-1")
    except ValueError:
        return ""


def coinbase_text(tx: Tx) -> str:
    return "".join(ch for ch in _decode(tx.vin[0].scriptsig_hex) if 32 <= ord(ch) < 127)


def match_pool(scriptsig_hex: str, rules: Sequence[tuple[str, str]]) -> str | None:
    text = _decode(scriptsig_hex)
    for tag, pool in rules:
        if tag and tag in text:
            return pool
    return None


@heuristic("H-COINBASE")
async def coinbase_heuristic(tx: Tx, ctx: Context) -> list[Finding]:
    if not tx.is_coinbase:
        return []
    text = coinbase_text(tx)
    pool = match_pool(tx.vin[0].scriptsig_hex, ctx.coinbase_rules)
    if pool:
        return [Finding(heuristic="H-COINBASE", subject=tx_subject(tx.txid), label=f"miner:{pool}",
                        confidence=0.9, evidence={"pool": pool, "coinbase_text": text})]
    return [Finding(heuristic="H-COINBASE", subject=tx_subject(tx.txid), label="miner:unknown",
                    confidence=0.5, evidence={"coinbase_text": text})]
```

`backend/btcintel/heuristics/flags.py`:
```python
"""Compact, offline per-transaction labels for graph nodes and lists."""

from __future__ import annotations

from btcintel.chain.models import Tx
from btcintel.heuristics.coinjoin import classify_coinjoin
from btcintel.heuristics.crosschain import xchain_markers
from btcintel.heuristics.patterns import fanin_shape, fanout_shape, peel_shape


def tx_flags(tx: Tx) -> list[str]:
    flags = []
    if tx.is_coinbase:
        flags.append("coinbase")
    m = classify_coinjoin(tx)
    if m is not None:
        flags.append(f"coinjoin:{m.kind}")
    if peel_shape(tx):
        flags.append("peel_step")
    fanout = fanout_shape(tx)
    if fanout:
        flags.append(fanout["label"])
    if fanin_shape(tx):
        flags.append("consolidation")
    flags.extend(label for label, _, _ in xchain_markers(tx))
    return flags
```

Update `all.py`:
```python
"""Import every detector module so its @heuristic registrations run."""

from btcintel.heuristics import (  # noqa: F401
    change,
    cioh,
    coinbase,
    coinjoin,
    crosschain,
    fingerprint,
    patterns,
)
```

- [ ] **Step 3: Flip the catalog entries, update the KB pages and render**

Set `status: implemented` and:
- `H-PEEL` → `btcintel.heuristics.patterns.peel_heuristic`
- `H-MOTIF-FANOUT` → `btcintel.heuristics.patterns.fanout_heuristic`
- `H-MOTIF-FANIN` → `btcintel.heuristics.patterns.fanin_heuristic`
- `H-XCHAIN` → `btcintel.heuristics.crosschain.crosschain_heuristic`
- `H-COINBASE` → `btcintel.heuristics.coinbase.coinbase_heuristic`

Update the KB pages, then run `uv run btcintel catalog render`.

- [ ] **Step 4: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest -v && uv run ruff check . && uv run btcintel catalog check`
Expected: all pass. The registry equals {H-FP, H-CJ, H-CIOH, H-CHG, H-PEEL, H-MOTIF-FANOUT, H-MOTIF-FANIN, H-XCHAIN, H-COINBASE}.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/heuristics backend/tests/heuristics catalog/heuristics.yaml docs/kb
git commit -m "feat(heuristics): peel/fan motifs, THORChain and Omni markers, miner attribution, tx flags

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Local address clustering (union-find + capped CIOH expansion)

**Files:**
- Create: `backend/btcintel/cluster/__init__.py`, `backend/btcintel/cluster/unionfind.py`, `backend/btcintel/cluster/expand.py`
- Test: `backend/tests/cluster/test_unionfind.py`, `backend/tests/cluster/test_expand.py`

**Interfaces:**
- Consumes: `open_intel_db`, `transaction`, `normalize_address`, `cioh_addresses`, `CallBudget`, `budget_scope`, `BudgetExceeded`, `SourceError`, `ChainSource`, `TagStore`, `Tag`.
- Produces:
  - `ClusterMeta(root, size, partial, capped, expanded_at, calls_used)` (pydantic)
  - `UnionFind(conn)`, with methods:
    - `root_of(a) -> str | None`
    - `find(a) -> str`, which creates a singleton cluster if missing
    - `size(root) -> int`
    - `union(a, b, *, txid=None, heuristic="H-CIOH") -> str`: union by size, with ties broken by the lexicographically smaller root
    - `members(root, limit=None) -> list[str]`, `meta(root) -> ClusterMeta | None`
    - `set_meta(root, *, partial=None, capped=None, calls_used_add=0, expanded_at=None)`
    - `links(root, limit=200) -> list[dict]`
  - `ExpandPolicy(max_addresses=2000, max_calls=400, max_txs_per_address=200)`
  - `Conflict(labels: list[str], addresses: list[str])`
  - `ExpandResult(root, size, partial, capped, calls_used, new_links, conflicts)`
  - `async expand_cluster(seed, chain, uf, tags, policy=None, progress=None) -> ExpandResult`
  - `cluster_tags(root, uf, tags, limit=10_000) -> list[Tag]`, `cluster_conflicts(root, uf, tags) -> list[Conflict]`

- [ ] **Step 1: Write the failing tests**

`backend/tests/cluster/test_unionfind.py`:
```python
from hypothesis import given, settings
from hypothesis import strategies as st

from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db


def uf() -> UnionFind:
    return UnionFind(open_intel_db(":memory:"))


def test_find_creates_singletons_and_union_merges():
    u = uf()
    assert u.root_of("a") is None
    assert u.find("a") == "a" and u.size("a") == 1
    root = u.union("a", "b", txid="t1")
    assert root == "a" and u.find("b") == "a" and u.size("a") == 2
    assert u.union("b", "a") == "a"
    assert sorted(u.members("a")) == ["a", "b"]
    assert u.links("a") == [{"a": "a", "b": "b", "txid": "t1", "heuristic": "H-CIOH"}]


def test_larger_cluster_absorbs_smaller_and_meta_merges():
    u = uf()
    u.union("a", "b")
    u.union("a", "c")
    u.set_meta("z", partial=False)
    u.find("z")
    u.set_meta("z", capped=True, calls_used_add=7)
    assert u.union("z", "c") == "a"
    meta = u.meta("a")
    assert meta.size == 4 and meta.capped and meta.calls_used == 7 and u.meta("z") is None


def test_bech32_addresses_are_normalised():
    u = uf()
    addr = "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"
    u.find(addr.upper())
    assert u.root_of(addr) == addr


@given(st.lists(st.tuples(st.integers(0, 11), st.integers(0, 11)), max_size=40))
@settings(max_examples=150, deadline=None)
def test_matches_reference_partition(pairs):
    u = uf()
    names = [f"addr{i}" for i in range(12)]
    parent = list(range(12))

    def ref(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        u.union(names[a], names[b])
        ra, rb = ref(a), ref(b)
        if ra != rb:
            parent[ra] = rb
    for i in range(12):
        for j in range(12):
            assert (u.find(names[i]) == u.find(names[j])) == (ref(i) == ref(j))
    roots = {u.find(n) for n in names}
    assert sum(u.size(r) for r in roots) == 12
    assert all(u.size(r) == len(u.members(r)) for r in roots)
```

`backend/tests/cluster/test_expand.py`:
```python
from btcintel.cluster.expand import ExpandPolicy, cluster_conflicts, expand_cluster
from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db
from btcintel.labels.store import Tag, TagStore
from tests import cj_samples as s
from tests.builders import mk_tx
from tests.fakes import FakeChain


def world():
    conn = open_intel_db(":memory:")
    tx1 = mk_tx([("A", 50_000), ("B", 60_000)], [("X", 100_000)])
    tx2 = mk_tx([("B", 70_000), ("C", 80_000)], [("Y", 140_000)])
    mix = s.whirlpool_mix()
    mix = mix.model_copy(update={"vin": [mix.vin[0].model_copy(update={
        "prevout": mix.vin[0].prevout.model_copy(update={"address": "C"})})] + mix.vin[1:]})
    tx4 = mk_tx([("D", 10_000)], [("Z", 9_000)])
    return FakeChain([tx1, tx2, mix, tx4]), UnionFind(conn), TagStore(conn)


async def test_expand_follows_cioh_and_skips_coinjoins():
    chain, uf, tags = world()
    events = []
    r = await expand_cluster("A", chain, uf, tags, progress=events.append)
    assert (r.root, r.size, r.new_links, r.partial, r.capped) == ("A", 3, 2, False, False)
    assert sorted(uf.members("A")) == ["A", "B", "C"]
    assert uf.root_of("bc1-sample-1") is None
    assert events and events[-1]["type"] == "progress"
    assert uf.meta("A").partial is False and uf.meta("A").calls_used == r.calls_used


async def test_expand_caps_cluster_size():
    chain, uf, tags = world()
    r = await expand_cluster("A", chain, uf, tags, ExpandPolicy(max_addresses=2))
    assert r.capped and r.partial and r.size == 2


async def test_expand_budget_marks_partial():
    chain, uf, tags = world()
    r = await expand_cluster("A", chain, uf, tags, ExpandPolicy(max_calls=1))
    assert r.partial and r.calls_used == 1


async def test_truncated_history_marks_partial():
    chain, uf, tags = world()
    r = await expand_cluster("B", chain, uf, tags, ExpandPolicy(max_txs_per_address=1))
    assert r.partial


async def test_conflicting_entity_labels_reported():
    chain, uf, tags = world()
    tags.add_many([
        Tag(address="A", label="Binance", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="C", label="Kraken", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="B", label="some person", category="individual", confidence="authority_data", source="s", pack="p"),
    ])
    r = await expand_cluster("A", chain, uf, tags)
    assert [c.labels for c in r.conflicts] == [["binance", "kraken"]]
    assert cluster_conflicts("A", uf, tags) == r.conflicts
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/cluster -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/cluster/__init__.py`: empty.

`backend/btcintel/cluster/unionfind.py`:
```python
"""Persistent union-find over addresses (SQLite). Union by size; roots are member addresses."""

from __future__ import annotations

import sqlite3
from typing import Any

from pydantic import BaseModel

from btcintel.chain.validate import normalize_address
from btcintel.db import transaction


class ClusterMeta(BaseModel):
    root: str
    size: int
    partial: bool
    capped: bool
    expanded_at: float | None
    calls_used: int


class UnionFind:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def root_of(self, address: str) -> str | None:
        row = self.conn.execute(
            "SELECT root FROM addr_cluster WHERE address = ?", (normalize_address(address),)
        ).fetchone()
        return row["root"] if row else None

    def find(self, address: str) -> str:
        a = normalize_address(address)
        root = self.root_of(a)
        if root is not None:
            return root
        with transaction(self.conn):
            self.conn.execute("INSERT INTO addr_cluster (address, root) VALUES (?, ?)", (a, a))
            self.conn.execute("INSERT OR IGNORE INTO clusters (root, size) VALUES (?, 1)", (a,))
        return a

    def size(self, root: str) -> int:
        row = self.conn.execute("SELECT size FROM clusters WHERE root = ?", (root,)).fetchone()
        return int(row["size"]) if row else 0

    def union(self, a: str, b: str, *, txid: str | None = None, heuristic: str = "H-CIOH") -> str:
        with transaction(self.conn):
            ra, rb = self.find(a), self.find(b)
            if txid is not None:
                self.conn.execute(
                    "INSERT OR IGNORE INTO cluster_links (a, b, txid, heuristic) VALUES (?, ?, ?, ?)",
                    (normalize_address(a), normalize_address(b), txid, heuristic),
                )
            if ra == rb:
                return ra
            sa, sb = self.size(ra), self.size(rb)
            if sa < sb or (sa == sb and rb < ra):
                ra, rb, sa, sb = rb, ra, sb, sa
            absorbed = self.conn.execute(
                "SELECT partial, capped, calls_used FROM clusters WHERE root = ?", (rb,)
            ).fetchone()
            self.conn.execute("UPDATE addr_cluster SET root = ? WHERE root = ?", (ra, rb))
            self.conn.execute(
                "UPDATE clusters SET size = ?, partial = MAX(partial, ?), capped = MAX(capped, ?), "
                "calls_used = calls_used + ? WHERE root = ?",
                (sa + sb, absorbed["partial"], absorbed["capped"], absorbed["calls_used"], ra),
            )
            self.conn.execute("DELETE FROM clusters WHERE root = ?", (rb,))
            return ra

    def members(self, root: str, limit: int | None = None) -> list[str]:
        rows = self.conn.execute(
            "SELECT address FROM addr_cluster WHERE root = ? ORDER BY address LIMIT ?",
            (root, -1 if limit is None else limit),
        )
        return [r["address"] for r in rows]

    def meta(self, root: str) -> ClusterMeta | None:
        r = self.conn.execute("SELECT * FROM clusters WHERE root = ?", (root,)).fetchone()
        if r is None:
            return None
        return ClusterMeta(root=r["root"], size=r["size"], partial=bool(r["partial"]),
                           capped=bool(r["capped"]), expanded_at=r["expanded_at"],
                           calls_used=r["calls_used"])

    def set_meta(self, root: str, *, partial: bool | None = None, capped: bool | None = None,
                 calls_used_add: int = 0, expanded_at: float | None = None) -> None:
        self.find(root)
        self.conn.execute(
            "UPDATE clusters SET partial = COALESCE(?, partial), capped = COALESCE(?, capped), "
            "calls_used = calls_used + ?, expanded_at = COALESCE(?, expanded_at) WHERE root = ?",
            (None if partial is None else int(partial), None if capped is None else int(capped),
             calls_used_add, expanded_at, self.find(root)),
        )

    def links(self, root: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT l.a, l.b, l.txid, l.heuristic FROM cluster_links l "
            "JOIN addr_cluster c ON c.address = l.a WHERE c.root = ? ORDER BY l.txid LIMIT ?",
            (root, limit),
        )
        return [dict(r) for r in rows]
```

`backend/btcintel/cluster/expand.py`:
```python
"""Capped cluster expansion: walk address histories and union co-spent inputs (H-CIOH)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import aclosing
from typing import Any

from pydantic import BaseModel, Field

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import SourceError
from btcintel.chain.source import ChainSource
from btcintel.chain.validate import normalize_address
from btcintel.cluster.unionfind import UnionFind
from btcintel.heuristics.cioh import cioh_addresses
from btcintel.labels.store import Tag, TagStore

ENTITY_MIN_CONFIDENCE = 50
NON_ENTITY_CATEGORIES = {"unknown", "victim", "individual", "organization", "perpetrator"}

Progress = Callable[[dict[str, Any]], None]


class ExpandPolicy(BaseModel):
    max_addresses: int = Field(2000, ge=1, le=100_000)
    max_calls: int = Field(400, ge=1, le=20_000)
    max_txs_per_address: int = Field(200, ge=1, le=10_000)


class Conflict(BaseModel):
    labels: list[str]
    addresses: list[str]


class ExpandResult(BaseModel):
    root: str
    size: int
    partial: bool
    capped: bool
    calls_used: int
    new_links: int
    conflicts: list[Conflict]


def cluster_tags(root: str, uf: UnionFind, tags: TagStore, limit: int = 10_000) -> list[Tag]:
    by_address = tags.for_addresses(uf.members(root, limit))
    return sorted((t for ts in by_address.values() for t in ts),
                  key=lambda t: (-t.confidence_level, t.label))


def cluster_conflicts(root: str, uf: UnionFind, tags: TagStore) -> list[Conflict]:
    names: dict[str, set[str]] = defaultdict(set)
    for t in cluster_tags(root, uf, tags):
        if t.confidence_level < ENTITY_MIN_CONFIDENCE or t.category in NON_ENTITY_CATEGORIES:
            continue
        names[(t.actor or t.label).strip().lower()].add(t.address)
    if len(names) <= 1:
        return []
    addresses = sorted({a for group in names.values() for a in group})[:50]
    return [Conflict(labels=sorted(names), addresses=addresses)]


async def expand_cluster(
    seed: str,
    chain: ChainSource,
    uf: UnionFind,
    tags: TagStore,
    policy: ExpandPolicy | None = None,
    progress: Progress | None = None,
) -> ExpandResult:
    policy = policy or ExpandPolicy()
    seed = normalize_address(seed)
    budget = CallBudget(policy.max_calls)
    queue = deque(uf.members(uf.find(seed)))
    visited: set[str] = set()
    new_links = 0
    partial = capped = False
    with budget_scope(budget):
        try:
            while queue and not capped:
                address = queue.popleft()
                if address in visited:
                    continue
                visited.add(address)
                seen = 0
                async with aclosing(chain.iter_address_txs(address, policy.max_txs_per_address)) as txs:
                    async for tx in txs:
                        seen += 1
                        linked = cioh_addresses(tx)
                        if not linked or address not in linked:
                            continue
                        for other in linked:
                            if uf.find(other) != uf.find(address):
                                uf.union(address, other, txid=tx.txid, heuristic="H-CIOH")
                                new_links += 1
                            if other not in visited:
                                queue.append(other)
                        if uf.size(uf.find(seed)) >= policy.max_addresses:
                            capped = True
                            break
                if seen >= policy.max_txs_per_address:
                    partial = True
                if progress:
                    progress({"type": "progress", "visited": len(visited), "queued": len(queue),
                              "size": uf.size(uf.find(seed)), "calls": budget.used})
        except (BudgetExceeded, SourceError):
            partial = True
    if capped or any(a not in visited for a in queue):
        partial = True
    root = uf.find(seed)
    uf.set_meta(root, partial=partial, capped=capped, calls_used_add=budget.used, expanded_at=time.time())
    return ExpandResult(root=root, size=uf.size(root), partial=partial, capped=capped,
                        calls_used=budget.used, new_links=new_links,
                        conflicts=cluster_conflicts(root, uf, tags))
```

- [ ] **Step 3: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/cluster -v && uv run ruff check .`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/cluster backend/tests/cluster
git commit -m "feat(cluster): persistent union-find and capped CIOH cluster expansion with conflict detection

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Taint models (H-TAINT)

**Files:**
- Create: `backend/btcintel/trace/__init__.py`, `backend/btcintel/trace/taint.py`
- Modify: `catalog/heuristics.yaml` (H-TAINT → implemented), `docs/kb/heuristics/h-taint.md`, regenerated index
- Test: `backend/tests/trace/test_taint.py`

**Interfaces:**
- Consumes: `Tx`.
- Produces:
  - `TaintMap = dict[int, float]`, `TAINT_MODELS = ("poison", "haircut", "fifo")`
  - Pure list functions `poison_forward`, `haircut_forward`, `fifo_forward`, `poison_backward`, `haircut_backward` and `fifo_backward`, each with signature `(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap`
  - `forward(model, tx, tainted_inputs) -> TaintMap` and `backward(model, tx, tainted_outputs) -> TaintMap`; `ValueError` for an unknown model

Semantics:
- Taint amounts are clamped to `[0, value]`.
- FIFO treats the tainted sats as the first sats of each input (forward) or output (backward), and maps positions in the input value stream onto the output stream. The fee sits at the end of the output stream.
- Haircut and FIFO are linear and never create taint.
- Poison taints every positive-value output fully.

Worked example (inputs 60,000 + 40,000 sats, where input 1 is tainted; outputs 70,000 + 29,000 sats; fee 1,000):

| Model | Output 0 | Output 1 |
|---|---|---|
| haircut | 28,000 | 11,600 |
| FIFO | 10,000 | 29,000 |
| poison | 70,000 | 29,000 |

- [ ] **Step 1: Write the failing tests**

`backend/tests/trace/test_taint.py`:
```python
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from btcintel.trace.taint import (
    backward,
    fifo_backward,
    fifo_forward,
    forward,
    haircut_backward,
    haircut_forward,
    poison_forward,
)
from tests.builders import mk_tx

INS, OUTS = [60_000, 40_000], [70_000, 29_000]


def test_worked_example():
    assert haircut_forward(INS, OUTS, {1: 40_000}) == pytest.approx({0: 28_000, 1: 11_600})
    assert fifo_forward(INS, OUTS, {1: 40_000}) == {0: 10_000, 1: 29_000}
    assert poison_forward(INS, OUTS, {1: 40_000}) == {0: 70_000, 1: 29_000}
    assert haircut_backward(INS, OUTS, {0: 70_000}) == pytest.approx({0: 42_000, 1: 28_000})
    assert fifo_backward(INS, OUTS, {1: 29_000}) == {1: 29_000}


def test_clamping_and_empty():
    assert haircut_forward(INS, OUTS, {0: -5, 7: 100}) == {}
    assert fifo_forward(INS, OUTS, {0: 10**12}) == {0: 60_000}
    assert poison_forward(INS, OUTS, {}) == {}


def test_tx_level_api_and_unknown_model():
    tx = mk_tx([("a", 60_000), ("b", 40_000)], [("c", 70_000), ("d", 29_000)])
    assert forward("fifo", tx, {1: 40_000}) == {0: 10_000, 1: 29_000}
    assert backward("haircut", tx, {0: 70_000}) == pytest.approx({0: 42_000, 1: 28_000})
    with pytest.raises(ValueError, match="unknown taint model"):
        forward("magic", tx, {})


@st.composite
def tx_values(draw):
    ins = draw(st.lists(st.integers(1, 10**8), min_size=1, max_size=6))
    fee = draw(st.integers(0, min(ins)))
    total = sum(ins) - fee
    k = draw(st.integers(1, 6))
    cuts = sorted(draw(st.lists(st.integers(0, total), min_size=k - 1, max_size=k - 1)))
    outs = [b - a for a, b in zip([0, *cuts], [*cuts, total], strict=True)]
    return ins, outs


def _taint(data, values):
    return {i: data.draw(st.integers(0, v)) for i, v in enumerate(values) if data.draw(st.booleans())}


@given(tx_values(), st.data())
@settings(max_examples=300, deadline=None)
def test_forward_models_conserve_and_bound(tv, data):
    ins, outs = tv
    taint = _taint(data, ins)
    for fn in (haircut_forward, fifo_forward):
        res = fn(ins, outs, taint)
        assert sum(res.values()) <= sum(taint.values()) + 1e-6
        assert all(res[j] <= outs[j] + 1e-6 for j in res)


@given(tx_values(), st.data())
@settings(max_examples=300, deadline=None)
def test_backward_models_conserve_and_bound(tv, data):
    ins, outs = tv
    taint = _taint(data, outs)
    for fn in (haircut_backward, fifo_backward):
        res = fn(ins, outs, taint)
        assert sum(res.values()) <= sum(taint.values()) + 1e-6
        assert all(res[i] <= ins[i] + 1e-6 for i in res)


@given(tx_values(), st.data())
@settings(max_examples=200, deadline=None)
def test_haircut_and_fifo_are_linear_in_inputs(tv, data):
    ins, outs = tv
    taint = _taint(data, ins)
    items = list(taint.items())
    a, b = dict(items[: len(items) // 2]), dict(items[len(items) // 2 :])
    for fn in (haircut_forward, fifo_forward):
        whole, pa, pb = fn(ins, outs, taint), fn(ins, outs, a), fn(ins, outs, b)
        for j in set(whole) | set(pa) | set(pb):
            assert whole.get(j, 0) == pytest.approx(pa.get(j, 0) + pb.get(j, 0), abs=1e-6)
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/trace/test_taint.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/trace/__init__.py`: empty.

`backend/btcintel/trace/taint.py`:
```python
"""H-TAINT: how much of each output derives from tainted inputs (and vice versa), per transaction."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from btcintel.chain.models import Tx

TaintMap = dict[int, float]
TAINT_MODELS = ("poison", "haircut", "fifo")
Model = Callable[[Sequence[int], Sequence[int], Mapping[int, float]], TaintMap]


def _clamp(values: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return {i: min(float(t), float(values[i])) for i, t in taint.items()
            if 0 <= i < len(values) and t > 0 and values[i] > 0}


def _starts(values: Sequence[int]) -> list[int]:
    out, acc = [], 0
    for v in values:
        out.append(acc)
        acc += v
    return out


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _map_ranges(src: Sequence[int], dst: Sequence[int], taint: TaintMap) -> TaintMap:
    """Tainted sats are the first `t` sats of each source slot; map them onto destination slots."""
    src_starts, dst_starts = _starts(src), _starts(dst)
    res: TaintMap = {}
    for i, amount in taint.items():
        a0, a1 = src_starts[i], src_starts[i] + amount
        for j, w in enumerate(dst):
            ov = _overlap(a0, a1, dst_starts[j], dst_starts[j] + w)
            if ov > 0:
                res[j] = res.get(j, 0.0) + ov
    return res


def poison_forward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return {j: float(v) for j, v in enumerate(outs) if v > 0} if _clamp(ins, taint) else {}


def haircut_forward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    t, total = _clamp(ins, taint), sum(ins)
    if not t or total <= 0:
        return {}
    fraction = sum(t.values()) / total
    return {j: v * fraction for j, v in enumerate(outs) if v > 0}


def fifo_forward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return _map_ranges(ins, outs, _clamp(ins, taint))


def poison_backward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return {i: float(v) for i, v in enumerate(ins) if v > 0} if _clamp(outs, taint) else {}


def haircut_backward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    t, total = _clamp(outs, taint), sum(ins)
    if not t or total <= 0:
        return {}
    amount = sum(t.values())
    return {i: amount * v / total for i, v in enumerate(ins) if v > 0}


def fifo_backward(ins: Sequence[int], outs: Sequence[int], taint: Mapping[int, float]) -> TaintMap:
    return _map_ranges(outs, ins, _clamp(outs, taint))


_FORWARD: dict[str, Model] = {"poison": poison_forward, "haircut": haircut_forward, "fifo": fifo_forward}
_BACKWARD: dict[str, Model] = {"poison": poison_backward, "haircut": haircut_backward, "fifo": fifo_backward}


def forward(model: str, tx: Tx, tainted_inputs: Mapping[int, float]) -> TaintMap:
    if model not in _FORWARD:
        raise ValueError(f"unknown taint model {model!r}")
    return _FORWARD[model]([i.value for i in tx.vin], [o.value for o in tx.vout], tainted_inputs)


def backward(model: str, tx: Tx, tainted_outputs: Mapping[int, float]) -> TaintMap:
    if model not in _BACKWARD:
        raise ValueError(f"unknown taint model {model!r}")
    return _BACKWARD[model]([i.value for i in tx.vin], [o.value for o in tx.vout], tainted_outputs)
```

- [ ] **Step 3: Flip H-TAINT in the catalog**

Set `H-TAINT` to `status: implemented` with `implemented_by: btcintel.trace.taint.forward`. Add the worked-example table to `docs/kb/heuristics/h-taint.md` ("Detection in btc-intel"), then run `uv run btcintel catalog render`.

- [ ] **Step 4: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest -v && uv run ruff check . && uv run btcintel catalog check`
Expected: all pass. The registry test ignores `family: taint`.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/trace backend/tests/trace catalog/heuristics.yaml docs/kb
git commit -m "feat(trace): poison, haircut and FIFO taint models with property tests (H-TAINT)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Label lookup, trace engine (forward/backward, streaming) and peel-chain follower

**Files:**
- Create: `backend/btcintel/labels/lookup.py`, `backend/btcintel/trace/graph.py`, `backend/btcintel/trace/engine.py`, `backend/btcintel/trace/peel.py`, `backend/tests/scenario.py`
- Modify: `backend/tests/builders.py` (add `ADDR`)
- Test: `backend/tests/labels/test_lookup.py`, `backend/tests/trace/test_engine.py`, `backend/tests/trace/test_peel.py`

**Interfaces:**
- Consumes: `TagStore`, `Taxonomy`, `UnionFind`, `RISK_ORDER`, `classify_coinjoin`, `MULTIPARTY_KINDS`, `remainder_output`, `peel_shape`, `is_multiparty`, `tx_flags`, `taint.forward/backward`, `CallBudget`, `budget_scope`, `BudgetExceeded`, `SourceError`, `ChainSource`, `is_txid`, `is_address`, `normalize_address`.
- Produces:
  - `AddressInfo(address, tags: tuple[Tag,...], cluster, category, label, risk, stop_category)`, with `.to_dict()`
  - `LabelLookup(tags, taxonomy, uf=None, stop_categories=None, cluster_member_limit=5000)`, with `.lookup(address) -> AddressInfo` (cached; the address's own tags come before those inherited from its cluster) and `.stop: set[str]`
  - `GraphNode(id, kind: "tx"|"address"|"script", label, data)`, `GraphEdge(id, source, target, value, taint)`, `Stop(node, reason, taint, detail)`
    - node IDs: `tx:<txid>`, `addr:<address>`, `script:<txid>:<n>`
    - edge IDs: `in:<txid>:<vin>` (address→tx) and `out:<txid>:<vout>` (tx→address or script)
  - `GraphBuilder(labels, emit=None)`, with `add_tx`, `add_output`, `add_input_taint`, `stop`, `.nodes`, `.edges`, `.stops`, `.txs` and `.truncated`
  - `tx_node_id(txid)`, `addr_node_id(address)`
  - `TracePolicy`:

    | Field | Default |
    |---|---|
    | `direction` | `"forward"` |
    | `max_hops` | 6 |
    | `max_txs` | 200 |
    | `max_calls` | 600 |
    | `min_value_sats` | 10,000 |
    | `taint_model` | `"haircut"` |
    | `stop_categories` | `None` (taxonomy defaults) |
    | `coinjoin` | `"stop"` |
    | `peel_mode` | `False` |
    | `max_address_txs` | 50 |

  - `TraceSeed(txid=None, vout=None, address=None)`: exactly one of txid/address; validated and normalised
  - `TraceResult(seed, policy, nodes, edges, stops, incomplete, reason, calls_used, txs_expanded)`
  - `async trace(seed, policy, *, chain, labels, emit=None) -> TraceResult`
  - `PeelStep(txid, remainder_vout, remainder_value, peels)`, `PeelChain(start_txid, steps, end_reason, end_txid, total_peeled)`
  - `async follow_peel_chain(start_txid, chain, labels, max_steps=50) -> PeelChain`
  - Stream events (the `emit` payloads, which Plan 3 consumes):
    - `{"type":"nodes","items":[GraphNode…]}`
    - `{"type":"edges","items":[GraphEdge…]}`
    - `{"type":"stop","item":Stop}`
    - `{"type":"done","incomplete":bool,"reason":str|None,"calls_used":int}`

Forward algorithm: a max-heap on tainted value holds outputs to follow, `(taint, hop, txid, vout)`. For each popped output:
1. Stop with `min_value` if the taint is below `min_value_sats`.
2. Stop with `max_hops` if the hop count exceeds `max_hops`.
3. Stop with `unspent` if the outspend is unspent.
4. Stop with `max_txs` (marking the trace truncated) if adding the spending tx would exceed `max_txs`.
5. Otherwise add the spending tx. If it is a multi-party CoinJoin and `coinjoin == "stop"`, stop with `coinjoin`.
6. Otherwise propagate with the taint model (poison propagates once per tx). In peel mode, only the remainder output is followed and the other outputs stop with `peel_off`.
7. For every output that receives taint: if its address carries a stop-category tag, stop with `labeled`; otherwise push it.

Backward works the same way over inputs: stop with `labeled` when the funding address has a stop-category tag, stop with `coinbase` at newly mined coins, and propagate through parents with the backward taint model.

- [ ] **Step 1: Add valid test addresses and the scenario**

Append to `backend/tests/builders.py`:
```python
# Valid mainnet addresses for tests that need real address syntax (seeds, API paths).
ADDR = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6",
    "3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4", "32fbAZMTaQxNd2fAue1PgsiPgWfcsHBQQt",
    "112D2adLM3UKy4Z4giRbReR6gjWuvHUqB", "31h38a54tFMrR8kzBnP2241MFD2EUHtGha",
    "bc1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysn4v0345",
    "bc1pqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0sg5tmnz",
    "1AXeFwAnsd1BkvBwPumsNnjzp4sAEUwyMX", "1Ep9h83bhzyjoRiCkG7e45bHRD3ApZh4QS",
    "13qpzTcRsRnaG4e4fZgwr2Y3qf8fZktKUX", "1J5VmAoXLfwsT4h18hJTLtFejsVV7gTSAK",
    "bc1qnv4s80dwudw0ts7nxq4t2s5hgr5kzmnrfh4rmw", "12aNKp2iDKuhEde2YfPdd4DFGenRUTKupL",
    "17TMc2UkVRSga2yYvuxSD9Q1XyB2EPRjTF",
]
```

`backend/tests/scenario.py`:
```python
"""A small theft → laundering graph used by trace and API tests."""

from dataclasses import dataclass

from btcintel.catalog.loader import load_catalog
from btcintel.chain.models import Tx
from btcintel.db import open_intel_db
from btcintel.labels.lookup import LabelLookup
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir
from tests.builders import ADDR, mk_tx

V, H1, H2, H3, EX, M, U = ADDR[0], ADDR[1], ADDR[4], ADDR[5], ADDR[2], ADDR[3], ADDR[8]


@dataclass
class Scenario:
    theft: Tx
    t1: Tx
    t2: Tx
    t3: Tx

    @property
    def txs(self) -> list[Tx]:
        return [self.theft, self.t1, self.t2, self.t3]


def build_scenario() -> Scenario:
    """V --theft--> H1 (600k) / H2 (399k); H1 -> EX (exchange, 100k) + H3 (499k) -> U (unspent);
    H2 -> M (mixer)."""
    theft = mk_tx([(V, 1_000_000)], [(H1, 600_000), (H2, 399_000)])
    t1 = mk_tx([(theft, 0)], [(EX, 100_000), (H3, 499_000)])
    t2 = mk_tx([(t1, 1)], [(U, 498_000)])
    t3 = mk_tx([(theft, 1)], [(M, 398_000)])
    return Scenario(theft, t1, t2, t3)


def scenario_tags() -> list[Tag]:
    return [
        Tag(address=EX, label="Example Exchange", category="exchange", confidence="authority_data",
            source="test", pack="test"),
        Tag(address=M, label="Example Mixer", category="mixing_service", confidence="authority_data",
            source="test", pack="test"),
    ]


def make_labels(extra_tags: list[Tag] | None = None, stop_categories=None) -> LabelLookup:
    store = TagStore(open_intel_db(":memory:"))
    store.add_many(scenario_tags() + (extra_tags or []))
    return LabelLookup(store, Taxonomy.from_catalog(load_catalog(catalog_dir())),
                       stop_categories=stop_categories)
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/labels/test_lookup.py`:
```python
from btcintel.catalog.loader import load_catalog
from btcintel.cluster.unionfind import UnionFind
from btcintel.db import open_intel_db
from btcintel.labels.lookup import LabelLookup
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy
from btcintel.paths import catalog_dir

TAX = Taxonomy.from_catalog(load_catalog(catalog_dir()))


def test_own_and_cluster_tags_risk_and_stop():
    conn = open_intel_db(":memory:")
    tags, uf = TagStore(conn), UnionFind(conn)
    uf.union("hot", "deposit")
    tags.add_many([
        Tag(address="hot", label="Binance", category="exchange", confidence="authority_data", source="s", pack="p"),
        Tag(address="bad", label="OFAC person", category="individual", abuse="sanctioned",
            confidence="authority_data", source="s", pack="p"),
    ])
    lookup = LabelLookup(tags, TAX, uf)
    dep = lookup.lookup("deposit")
    assert dep.cluster == "deposit" or dep.cluster == "hot"
    assert dep.label == "Binance" and dep.category == "exchange" and dep.stop_category == "exchange"
    assert dep.risk == "low"
    bad = lookup.lookup("bad")
    assert bad.risk == "severe" and bad.stop_category is None and bad.cluster is None
    none = lookup.lookup("nobody")
    assert (none.label, none.risk, none.tags) == (None, "none", ())
    assert LabelLookup(tags, TAX, uf, stop_categories=[]).lookup("hot").stop_category is None
    assert dep.to_dict()["tags"][0]["label"] == "Binance"
```

`backend/tests/trace/test_engine.py`:
```python
import pytest

from btcintel.trace.engine import TracePolicy, TraceSeed, trace
from tests import cj_samples as s
from tests.builders import ADDR, mk_tx
from tests.fakes import FakeChain
from tests.scenario import EX, H1, H3, M, U, build_scenario, make_labels


def stops(result):
    return {(st.node, st.reason) for st in result.stops}


def tx_ids(result):
    return {n.id for n in result.nodes if n.kind == "tx"}


async def test_forward_trace_reaches_services_and_unspent():
    sc = build_scenario()
    events = []
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(), chain=FakeChain(sc.txs),
                    labels=make_labels(), emit=events.append)
    assert {(f"addr:{EX}", "labeled"), (f"addr:{M}", "labeled"), (f"addr:{U}", "unspent")} <= stops(r)
    assert tx_ids(r) == {f"tx:{t.txid}" for t in sc.txs}
    edges = {e.id: e for e in r.edges}
    assert edges[f"out:{sc.t1.txid}:0"].taint == pytest.approx(100_000)
    assert edges[f"out:{sc.t2.txid}:0"].taint == pytest.approx(498_000)
    assert not r.incomplete and r.txs_expanded == 4
    assert {e["type"] for e in events} >= {"nodes", "edges", "stop", "done"} and events[-1]["type"] == "done"


async def test_max_hops():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(max_hops=1), chain=FakeChain(sc.txs),
                    labels=make_labels())
    assert f"tx:{sc.t2.txid}" not in tx_ids(r) and (f"addr:{H3}", "max_hops") in stops(r)


async def test_min_value():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(min_value_sats=450_000),
                    chain=FakeChain(sc.txs), labels=make_labels())
    assert f"tx:{sc.t3.txid}" not in tx_ids(r)
    assert any(reason == "min_value" for _, reason in stops(r))


async def test_coinjoin_stop_and_through():
    seed = mk_tx([(ADDR[9], 2_000_000)], [(ADDR[10], 1_006_050), (ADDR[11], 900_000)])
    mix = s.whirlpool_mix()
    mix = mix.model_copy(update={"vin": [mix.vin[0].model_copy(update={
        "prev_txid": seed.txid, "prev_vout": 0, "prevout": seed.vout[0]})] + mix.vin[1:]})
    chain = FakeChain([seed, mix])
    stopped = await trace(TraceSeed(txid=seed.txid, vout=0), TracePolicy(), chain=chain, labels=make_labels())
    assert (f"tx:{mix.txid}", "coinjoin") in stops(stopped)
    through = await trace(TraceSeed(txid=seed.txid, vout=0), TracePolicy(coinjoin="through"),
                          chain=chain, labels=make_labels())
    assert sum(1 for _, reason in stops(through) if reason == "unspent") == 5


async def test_peel_mode_follows_remainder():
    a = ADDR
    p0 = mk_tx([(a[0], 10_000_000)], [(a[1], 500_000), (a[2], 9_490_000)])
    p1 = mk_tx([(p0, 1)], [(a[3], 400_000), (a[4], 9_080_000)])
    p2 = mk_tx([(p1, 1)], [(a[5], 300_000), (a[6], 8_770_000)])
    r = await trace(TraceSeed(txid=p0.txid, vout=1), TracePolicy(peel_mode=True),
                    chain=FakeChain([p0, p1, p2]), labels=make_labels())
    assert {(f"addr:{a[3]}", "peel_off"), (f"addr:{a[5]}", "peel_off"), (f"addr:{a[6]}", "unspent")} <= stops(r)


async def test_backward_to_coinbase_and_labeled_source():
    a = ADDR
    cb = mk_tx([(None, 0)], [(a[0], 312_500_000)], coinbase=True)
    t = mk_tx([(cb, 0)], [(a[1], 100_000_000), (a[2], 212_000_000)])
    t2 = mk_tx([(t, 0)], [(a[3], 99_000_000)])
    chain = FakeChain([cb, t, t2])
    r = await trace(TraceSeed(txid=t2.txid), TracePolicy(direction="backward"), chain=chain, labels=make_labels())
    assert (f"tx:{cb.txid}", "coinbase") in stops(r)
    from btcintel.labels.store import Tag
    labeled = make_labels([Tag(address=a[0], label="Exchange hot wallet", category="exchange",
                               confidence="authority_data", source="t", pack="t")])
    r2 = await trace(TraceSeed(txid=t2.txid), TracePolicy(direction="backward"), chain=chain, labels=labeled)
    assert (f"addr:{a[0]}", "labeled") in stops(r2) and f"tx:{cb.txid}" not in tx_ids(r2)


async def test_budget_exhaustion_marks_incomplete():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(max_calls=2), chain=FakeChain(sc.txs),
                    labels=make_labels())
    assert r.incomplete and "budget" in r.reason and r.calls_used == 2


async def test_source_error_mid_trace_marks_incomplete():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(), chain=FakeChain(sc.txs, fail_on={sc.t1.txid}),
                    labels=make_labels())
    assert r.incomplete and "chain source failed" in r.reason


async def test_max_txs_truncates():
    sc = build_scenario()
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(max_txs=2), chain=FakeChain(sc.txs),
                    labels=make_labels())
    assert r.incomplete and "max_txs" in r.reason and len(tx_ids(r)) == 2


async def test_address_seed():
    sc = build_scenario()
    r = await trace(TraceSeed(address=H1), TracePolicy(), chain=FakeChain(sc.txs), labels=make_labels())
    assert f"tx:{sc.t1.txid}" in tx_ids(r)


async def test_poison_counts_each_tx_once():
    sc = build_scenario()
    join = mk_tx([(sc.theft, 0), (sc.theft, 1)], [(ADDR[12], 998_000)])
    chain = FakeChain([sc.theft, join])
    r = await trace(TraceSeed(txid=sc.theft.txid), TracePolicy(taint_model="poison"), chain=chain,
                    labels=make_labels())
    edges = {e.id: e for e in r.edges}
    assert edges[f"out:{join.txid}:0"].taint == pytest.approx(998_000)


@pytest.mark.parametrize("kwargs", [{}, {"txid": "zz"}, {"address": "nope"},
                                    {"txid": "ab" * 32, "address": ADDR[0]},
                                    {"address": ADDR[0], "vout": 1}])
def test_invalid_seeds(kwargs):
    with pytest.raises(ValueError):
        TraceSeed(**kwargs)


def test_seed_normalisation():
    assert TraceSeed(txid="AB" * 32).txid == "ab" * 32
    assert TraceSeed(address=ADDR[1].upper()).address == ADDR[1]
```

`backend/tests/trace/test_peel.py`:
```python
from btcintel.labels.store import Tag
from btcintel.trace.peel import follow_peel_chain
from tests import cj_samples as s
from tests.builders import ADDR, mk_tx
from tests.fakes import FakeChain
from tests.scenario import make_labels

a = ADDR


def chain3():
    p0 = mk_tx([(a[0], 10_000_000)], [(a[1], 500_000), (a[2], 9_490_000)])
    p1 = mk_tx([(p0, 1)], [(a[3], 400_000), (a[4], 9_080_000)])
    p2 = mk_tx([(p1, 1)], [(a[5], 300_000), (a[6], 8_770_000)])
    return p0, p1, p2


async def test_follows_until_unspent():
    p0, p1, p2 = chain3()
    pc = await follow_peel_chain(p0.txid, FakeChain([p0, p1, p2]), make_labels())
    assert [st.txid for st in pc.steps] == [p0.txid, p1.txid, p2.txid]
    assert pc.end_reason == "unspent" and pc.end_txid == p2.txid
    assert pc.total_peeled == 1_200_000 and pc.steps[0].peels[0]["address"] == a[1]


async def test_stops_at_labeled_remainder():
    p0, p1, p2 = chain3()
    labels = make_labels([Tag(address=a[4], label="Exchange", category="exchange",
                              confidence="authority_data", source="t", pack="t")])
    pc = await follow_peel_chain(p0.txid, FakeChain([p0, p1, p2]), labels)
    assert pc.end_reason == "labeled" and len(pc.steps) == 2


async def test_not_peel_shaped_and_coinjoin():
    odd = mk_tx([(a[0], 1_000_000)], [(a[1], 500_000), (a[2], 499_000)])
    assert (await follow_peel_chain(odd.txid, FakeChain([odd]), make_labels())).end_reason == "not_peel_shaped"
    mix = s.whirlpool_mix()
    assert (await follow_peel_chain(mix.txid, FakeChain([mix]), make_labels())).end_reason == "coinjoin"
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/labels/test_lookup.py tests/trace -v`
Expected: FAIL.

- [ ] **Step 3: Implement the label lookup**

`backend/btcintel/labels/lookup.py`:
```python
"""Per-address attribution view: own tags, tags inherited from the address's cluster, risk, stops."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from btcintel.catalog.schema import RISK_ORDER
from btcintel.chain.validate import normalize_address
from btcintel.cluster.unionfind import UnionFind
from btcintel.labels.store import Tag, TagStore
from btcintel.labels.taxonomy import Taxonomy


@dataclass(frozen=True)
class AddressInfo:
    address: str
    tags: tuple[Tag, ...]
    cluster: str | None
    category: str | None
    label: str | None
    risk: str
    stop_category: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address, "tags": [t.model_dump() for t in self.tags[:10]],
            "cluster": self.cluster, "category": self.category, "label": self.label,
            "risk": self.risk, "stop_category": self.stop_category,
        }


def _rank(t: Tag) -> tuple[int, str]:
    return (-t.confidence_level, t.label)


class LabelLookup:
    def __init__(self, tags: TagStore, taxonomy: Taxonomy, uf: UnionFind | None = None,
                 stop_categories: Iterable[str] | None = None, cluster_member_limit: int = 5000) -> None:
        self.tags = tags
        self.taxonomy = taxonomy
        self.uf = uf
        self.stop = set(stop_categories) if stop_categories is not None else taxonomy.default_stop_categories()
        self.cluster_member_limit = cluster_member_limit
        self._cache: dict[str, AddressInfo] = {}
        self._cluster_tags: dict[str, list[Tag]] = {}

    def lookup(self, address: str) -> AddressInfo:
        address = normalize_address(address)
        cached = self._cache.get(address)
        if cached is not None:
            return cached
        own = sorted(self.tags.for_address(address), key=_rank)
        root = self.uf.root_of(address) if self.uf else None
        inherited: list[Tag] = []
        if root is not None and self.uf is not None:
            if root not in self._cluster_tags:
                members = self.uf.members(root, self.cluster_member_limit)
                self._cluster_tags[root] = [t for ts in self.tags.for_addresses(members).values() for t in ts]
            inherited = sorted((t for t in self._cluster_tags[root] if t.address != address), key=_rank)
        ordered = own + inherited
        best = ordered[0] if ordered else None
        risk = max((self.taxonomy.risk_of_tag(t) for t in ordered), key=RISK_ORDER.__getitem__, default="none")
        stop = next((t.category for t in ordered if t.category in self.stop), None)
        info = AddressInfo(address=address, tags=tuple(ordered), cluster=root,
                           category=best.category if best else None, label=best.label if best else None,
                           risk=risk, stop_category=stop)
        self._cache[address] = info
        return info
```

- [ ] **Step 4: Implement the graph builder**

`backend/btcintel/trace/graph.py`:
```python
"""Incrementally built address↔transaction graph with streaming events."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from btcintel.chain.models import Tx
from btcintel.heuristics.flags import tx_flags
from btcintel.labels.lookup import LabelLookup

StopReason = Literal["unspent", "labeled", "coinjoin", "max_hops", "min_value", "max_txs", "coinbase", "peel_off"]
Emit = Callable[[dict[str, Any]], None]


class GraphNode(BaseModel):
    id: str
    kind: Literal["tx", "address", "script"]
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    value: int
    taint: float = 0.0


class Stop(BaseModel):
    node: str
    reason: StopReason
    taint: float = 0.0
    detail: str = ""


def tx_node_id(txid: str) -> str:
    return f"tx:{txid}"


def addr_node_id(address: str) -> str:
    return f"addr:{address}"


class GraphBuilder:
    def __init__(self, labels: LabelLookup, emit: Emit | None = None) -> None:
        self.labels = labels
        self.emit = emit
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, GraphEdge] = {}
        self.stops: list[Stop] = []
        self.txs: dict[str, Tx] = {}
        self.truncated = False

    def _send(self, kind: str, items: list[BaseModel]) -> None:
        if self.emit and items:
            self.emit({"type": kind, "items": [i.model_dump() for i in items]})

    def _address_node(self, address: str) -> GraphNode | None:
        nid = addr_node_id(address)
        if nid in self.nodes:
            return None
        info = self.labels.lookup(address)
        node = GraphNode(id=nid, kind="address", label=info.label or f"{address[:8]}…{address[-4:]}",
                         data=info.to_dict())
        self.nodes[nid] = node
        return node

    def add_tx(self, tx: Tx) -> bool:
        if tx.txid in self.txs:
            return False
        self.txs[tx.txid] = tx
        node = GraphNode(id=tx_node_id(tx.txid), kind="tx", label=tx.txid[:8], data={
            "txid": tx.txid, "block_height": tx.status.block_height, "block_time": tx.status.block_time,
            "confirmed": tx.status.confirmed, "fee": tx.fee, "n_in": len(tx.vin), "n_out": len(tx.vout),
            "value": tx.output_value, "flags": tx_flags(tx),
        })
        self.nodes[node.id] = node
        new_nodes: list[BaseModel] = [node]
        new_edges: list[BaseModel] = []
        for txin in tx.vin:
            if txin.address is None:
                continue
            an = self._address_node(txin.address)
            if an:
                new_nodes.append(an)
            edge = GraphEdge(id=f"in:{tx.txid}:{txin.n}", source=addr_node_id(txin.address),
                             target=node.id, value=txin.value)
            self.edges[edge.id] = edge
            new_edges.append(edge)
        self._send("nodes", new_nodes)
        self._send("edges", new_edges)
        return True

    def add_output(self, tx: Tx, n: int, taint: float = 0.0) -> str:
        out = tx.vout[n]
        target = addr_node_id(out.address) if out.address else f"script:{tx.txid}:{n}"
        new_nodes: list[BaseModel] = []
        if out.address:
            an = self._address_node(out.address)
            if an:
                new_nodes.append(an)
        elif target not in self.nodes:
            node = GraphNode(id=target, kind="script", label=out.script_type.upper(),
                             data={"script_type": out.script_type, "value": out.value})
            self.nodes[target] = node
            new_nodes.append(node)
        eid = f"out:{tx.txid}:{n}"
        prev = self.edges.get(eid)
        edge = GraphEdge(id=eid, source=tx_node_id(tx.txid), target=target, value=out.value,
                         taint=(prev.taint if prev else 0.0) + taint)
        self.edges[eid] = edge
        self._send("nodes", new_nodes)
        self._send("edges", [edge])
        return target

    def add_input_taint(self, tx: Tx, vin: int, taint: float) -> None:
        eid = f"in:{tx.txid}:{vin}"
        edge = self.edges.get(eid)
        if edge is None:
            return
        self.edges[eid] = edge.model_copy(update={"taint": edge.taint + taint})
        self._send("edges", [self.edges[eid]])

    def stop(self, node: str, reason: StopReason, taint: float = 0.0, detail: str = "") -> None:
        stop = Stop(node=node, reason=reason, taint=round(taint, 2), detail=detail)
        self.stops.append(stop)
        if self.emit:
            self.emit({"type": "stop", "item": stop.model_dump()})
```

- [ ] **Step 5: Implement the engine and the peel follower**

`backend/btcintel/trace/engine.py`:
```python
"""Follow-the-money tracing: expand the highest tainted value first, forward or backward."""

from __future__ import annotations

import heapq
import itertools
from contextlib import aclosing
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from btcintel.chain.budget import BudgetExceeded, CallBudget, budget_scope
from btcintel.chain.errors import SourceError
from btcintel.chain.models import Tx
from btcintel.chain.source import ChainSource
from btcintel.chain.validate import is_address, is_txid, normalize_address
from btcintel.heuristics.change import remainder_output
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, classify_coinjoin
from btcintel.labels.lookup import LabelLookup
from btcintel.trace import taint as taint_models
from btcintel.trace.graph import Emit, GraphBuilder, GraphEdge, GraphNode, Stop, addr_node_id, tx_node_id


class TracePolicy(BaseModel):
    direction: Literal["forward", "backward"] = "forward"
    max_hops: int = Field(6, ge=1, le=50)
    max_txs: int = Field(200, ge=1, le=5000)
    max_calls: int = Field(600, ge=1, le=50_000)
    min_value_sats: int = Field(10_000, ge=0)
    taint_model: Literal["poison", "haircut", "fifo"] = "haircut"
    stop_categories: list[str] | None = None
    coinjoin: Literal["stop", "through"] = "stop"
    peel_mode: bool = False
    max_address_txs: int = Field(50, ge=1, le=1000)


class TraceSeed(BaseModel):
    txid: str | None = None
    vout: int | None = Field(None, ge=0)
    address: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> TraceSeed:
        if (self.txid is None) == (self.address is None):
            raise ValueError("give exactly one of txid or address")
        if self.txid is not None:
            if not is_txid(self.txid):
                raise ValueError("invalid txid")
            self.txid = self.txid.lower()
        else:
            if not is_address(self.address or ""):
                raise ValueError("invalid address")
            if self.vout is not None:
                raise ValueError("vout only applies to a txid seed")
            self.address = normalize_address(self.address or "")
        return self


class TraceResult(BaseModel):
    seed: TraceSeed
    policy: TracePolicy
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    stops: list[Stop]
    incomplete: bool
    reason: str | None = None
    calls_used: int
    txs_expanded: int


async def trace(seed: TraceSeed, policy: TracePolicy, *, chain: ChainSource, labels: LabelLookup,
                emit: Emit | None = None) -> TraceResult:
    graph = GraphBuilder(labels, emit)
    budget = CallBudget(policy.max_calls)
    incomplete, reason = False, None
    with budget_scope(budget):
        try:
            if policy.direction == "forward":
                await _forward(seed, policy, chain, labels, graph)
            else:
                await _backward(seed, policy, chain, labels, graph)
        except BudgetExceeded as e:
            incomplete, reason = True, str(e)
        except SourceError as e:
            incomplete, reason = True, f"chain source failed: {e}"
    if graph.truncated and not incomplete:
        incomplete, reason = True, f"stopped after {policy.max_txs} transactions (max_txs)"
    if emit:
        emit({"type": "done", "incomplete": incomplete, "reason": reason, "calls_used": budget.used})
    return TraceResult(seed=seed, policy=policy, nodes=list(graph.nodes.values()),
                       edges=list(graph.edges.values()), stops=graph.stops, incomplete=incomplete,
                       reason=reason, calls_used=budget.used, txs_expanded=len(graph.txs))


def _is_stopping_coinjoin(tx: Tx, policy: TracePolicy) -> str | None:
    if policy.coinjoin != "stop":
        return None
    m = classify_coinjoin(tx)
    return m.kind if m is not None and m.kind in MULTIPARTY_KINDS else None


async def _forward(seed: TraceSeed, policy: TracePolicy, chain: ChainSource, labels: LabelLookup,
                   g: GraphBuilder) -> None:
    heap: list[tuple[float, int, int, str, int]] = []
    counter = itertools.count()
    poisoned: set[str] = set()

    def follow(tx: Tx, n: int, amount: float, hop: int) -> None:
        target = g.add_output(tx, n, amount)
        out = tx.vout[n]
        if out.address is None:
            return
        info = labels.lookup(out.address)
        if info.stop_category:
            g.stop(target, "labeled", amount, f"{info.stop_category}: {info.label}")
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
                        follow(tx, out.n, float(out.value), 1)

    while heap:
        neg, hop, _, txid, vout = heapq.heappop(heap)
        amount = -neg
        node = addr_node_id(g.txs[txid].vout[vout].address or "")
        if amount < policy.min_value_sats:
            g.stop(node, "min_value", amount)
            continue
        if hop > policy.max_hops:
            g.stop(node, "max_hops", amount)
            continue
        spends = await chain.get_outspends(txid)
        sp = spends[vout] if vout < len(spends) else None
        if sp is None or not sp.spent or sp.txid is None or sp.vin is None:
            g.stop(node, "unspent", amount)
            continue
        if sp.txid not in g.txs and len(g.txs) >= policy.max_txs:
            g.truncated = True
            g.stop(node, "max_txs", amount)
            continue
        child = await chain.get_tx(sp.txid)
        g.add_tx(child)
        g.add_input_taint(child, sp.vin, amount)
        cj_kind = _is_stopping_coinjoin(child, policy)
        if cj_kind:
            g.stop(tx_node_id(child.txid), "coinjoin", amount, cj_kind)
            continue
        if policy.taint_model == "poison":
            if child.txid in poisoned:
                continue
            poisoned.add(child.txid)
        delta = taint_models.forward(policy.taint_model, child, {sp.vin: amount})
        targets = sorted(delta.items())
        if policy.peel_mode:
            keep = remainder_output(child)
            for n, t in targets:
                if n != keep and t > 0:
                    g.stop(g.add_output(child, n, t), "peel_off", t)
            targets = [(keep, delta.get(keep, 0.0))] if keep is not None else []
        for n, t in targets:
            if t > 0:
                follow(child, n, t, hop + 1)


async def _backward(seed: TraceSeed, policy: TracePolicy, chain: ChainSource, labels: LabelLookup,
                    g: GraphBuilder) -> None:
    heap: list[tuple[float, int, int, str, int]] = []
    counter = itertools.count()

    def push(amount: float, hop: int, txid: str, vin: int) -> None:
        heapq.heappush(heap, (-amount, hop, next(counter), txid, vin))

    def seed_outputs(tx: Tx, tainted: dict[int, float]) -> None:
        g.add_tx(tx)
        for n, t in tainted.items():
            g.add_output(tx, n, t)
        if tx.is_coinbase:
            g.stop(tx_node_id(tx.txid), "coinbase", sum(tainted.values()), "newly mined coins")
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
                    seed_outputs(tx, received)

    while heap:
        neg, hop, _, txid, vin = heapq.heappop(heap)
        amount = -neg
        txin = g.txs[txid].vin[vin]
        node = addr_node_id(txin.address) if txin.address else tx_node_id(txid)
        if amount < policy.min_value_sats:
            g.stop(node, "min_value", amount)
            continue
        if hop > policy.max_hops:
            g.stop(node, "max_hops", amount)
            continue
        if txin.address:
            info = labels.lookup(txin.address)
            if info.stop_category:
                g.stop(node, "labeled", amount, f"{info.stop_category}: {info.label}")
                continue
        if txin.prev_txid not in g.txs and len(g.txs) >= policy.max_txs:
            g.truncated = True
            g.stop(node, "max_txs", amount)
            continue
        parent = await chain.get_tx(txin.prev_txid)
        g.add_tx(parent)
        g.add_output(parent, txin.prev_vout, amount)
        if parent.is_coinbase:
            g.stop(tx_node_id(parent.txid), "coinbase", amount, "newly mined coins")
            continue
        cj_kind = _is_stopping_coinjoin(parent, policy)
        if cj_kind:
            g.stop(tx_node_id(parent.txid), "coinjoin", amount, cj_kind)
            continue
        for i, t in sorted(taint_models.backward(policy.taint_model, parent, {txin.prev_vout: amount}).items()):
            if t > 0:
                push(t, hop + 1, parent.txid, i)
```

`backend/btcintel/trace/peel.py`:
```python
"""Follow a peel chain: repeatedly take the remainder output and record the peeled payments."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from btcintel.chain.budget import BudgetExceeded
from btcintel.chain.source import ChainSource
from btcintel.heuristics.change import remainder_output
from btcintel.heuristics.coinjoin import is_multiparty
from btcintel.heuristics.patterns import peel_shape
from btcintel.labels.lookup import LabelLookup


class PeelStep(BaseModel):
    txid: str
    remainder_vout: int
    remainder_value: int
    peels: list[dict[str, Any]]


class PeelChain(BaseModel):
    start_txid: str
    steps: list[PeelStep]
    end_reason: Literal["unspent", "not_peel_shaped", "max_steps", "labeled", "coinjoin", "budget"]
    end_txid: str | None = None
    total_peeled: int


async def follow_peel_chain(start_txid: str, chain: ChainSource, labels: LabelLookup,
                            max_steps: int = 50) -> PeelChain:
    steps: list[PeelStep] = []

    def done(reason: str, end: str | None) -> PeelChain:
        return PeelChain(start_txid=start_txid, steps=steps, end_reason=reason, end_txid=end,  # type: ignore[arg-type]
                         total_peeled=sum(p["value"] for s in steps for p in s.peels))

    txid = start_txid
    try:
        for _ in range(max_steps):
            tx = await chain.get_tx(txid)
            if is_multiparty(tx):
                return done("coinjoin", txid)
            keep = remainder_output(tx) if peel_shape(tx) else None
            if keep is None:
                return done("not_peel_shaped", txid)
            peels = [{"vout": o.n, "address": o.address, "value": o.value,
                      "label": labels.lookup(o.address).label if o.address else None}
                     for o in tx.spendable_outputs() if o.n != keep]
            steps.append(PeelStep(txid=tx.txid, remainder_vout=keep, remainder_value=tx.vout[keep].value,
                                  peels=peels))
            rem = tx.vout[keep]
            if rem.address and labels.lookup(rem.address).stop_category:
                return done("labeled", tx.txid)
            spends = await chain.get_outspends(tx.txid)
            sp = spends[keep] if keep < len(spends) else None
            if sp is None or not sp.spent or not sp.txid:
                return done("unspent", tx.txid)
            txid = sp.txid
    except BudgetExceeded:
        return done("budget", txid)
    return done("max_steps", txid)
```

- [ ] **Step 6: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest -v && uv run ruff check .`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/labels/lookup.py backend/btcintel/trace backend/tests/builders.py backend/tests/scenario.py backend/tests/labels/test_lookup.py backend/tests/trace
git commit -m "feat(trace): streaming forward/backward trace engine, label lookup and peel-chain follower

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Case files and background jobs

**Files:**
- Create: `backend/btcintel/cases/__init__.py`, `backend/btcintel/cases/store.py`, `backend/btcintel/jobs/__init__.py`, `backend/btcintel/jobs/manager.py`
- Test: `backend/tests/test_cases.py`, `backend/tests/test_jobs.py`

**Interfaces:**
- Produces:
  - `Case(id, name, notes, graph: dict, created_at, updated_at, watch: list[str])`, `CaseSummary(id, name, created_at, updated_at, nodes: int)`
  - `CaseStore(conn, clock=time.time)`, with methods:
    - `create(name, notes="", graph=None) -> Case`
    - `get(id) -> Case | None`
    - `list() -> list[CaseSummary]` (newest update first)
    - `update(id, *, name=None, notes=None, graph=None) -> Case | None`
    - `delete(id) -> bool`, `watch(id, address) -> bool`, `unwatch(id, address) -> bool`
    - `MAX_GRAPH_BYTES = 10_000_000`; a larger graph raises `ValueError`
  - `Job(id, kind, status, events, result, error, created_at)`, where status ∈ {running, done, error, cancelled}; `Job.push(event)` adds a `seq` field
  - `JobManager(max_jobs=200)`, with methods:
    - `start(kind, fn: Callable[[Callable[[dict], None]], Awaitable[Any]]) -> Job`
    - `get(id) -> Job | None`, `cancel(id) -> bool`
    - `async stream(id, start=0) -> AsyncIterator[dict]`, which yields events until the final `{"type":"status",…}`
    - finished jobs beyond `max_jobs` are evicted oldest first

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_cases.py`:
```python
import pytest

from btcintel.cases.store import MAX_GRAPH_BYTES, CaseStore
from btcintel.db import open_intel_db


def store():
    now = [1000.0]
    s = CaseStore(open_intel_db(":memory:"), clock=lambda: now[0])
    return s, now


def test_crud_and_ordering():
    s, now = store()
    a = s.create("Bitget 2026")
    now[0] = 1001
    b = s.create("Colonial", notes="ransom", graph={"nodes": [{"id": "x"}]})
    assert [c.id for c in s.list()] == [b.id, a.id] and s.list()[0].nodes == 1
    now[0] = 1002
    updated = s.update(a.id, notes="started", graph={"nodes": [1, 2]})
    assert updated.notes == "started" and updated.updated_at == 1002 and updated.name == "Bitget 2026"
    assert s.list()[0].id == a.id
    assert s.update("missing", notes="x") is None
    assert s.delete(b.id) and not s.delete(b.id) and s.get(b.id) is None


def test_watchlist_and_cascade():
    s, _ = store()
    c = s.create("w")
    assert s.watch(c.id, "bc1QNTNDGQFX46WKS63JEP34CJK3PW63ES86KP45C6")
    assert s.get(c.id).watch == ["bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6"]
    assert not s.watch("missing", "x")
    assert s.unwatch(c.id, "bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6") and s.get(c.id).watch == []
    s.watch(c.id, "a")
    s.delete(c.id)
    assert s.conn.execute("SELECT COUNT(*) FROM case_watch").fetchone()[0] == 0


def test_graph_size_limit():
    s, _ = store()
    with pytest.raises(ValueError, match="graph too large"):
        s.create("big", graph={"blob": "x" * (MAX_GRAPH_BYTES + 1)})
```

`backend/tests/test_jobs.py`:
```python
import asyncio

from btcintel.jobs.manager import JobManager


async def test_job_streams_events_then_result():
    jobs = JobManager()

    async def work(emit):
        emit({"type": "progress", "n": 1})
        await asyncio.sleep(0)
        emit({"type": "progress", "n": 2})
        return {"answer": 42}

    job = jobs.start("demo", work)
    events = [e async for e in jobs.stream(job.id)]
    assert [e["type"] for e in events] == ["progress", "progress", "status"]
    assert [e["seq"] for e in events] == [0, 1, 2]
    assert events[-1]["status"] == "done" and job.result == {"answer": 42}


async def test_failing_job_reports_error():
    jobs = JobManager()

    async def boom(emit):
        raise RuntimeError("bad")

    job = jobs.start("demo", boom)
    events = [e async for e in jobs.stream(job.id)]
    assert job.status == "error" and "RuntimeError: bad" in job.error and events[-1]["status"] == "error"


async def test_cancel_and_late_subscriber():
    jobs = JobManager()
    started = asyncio.Event()

    async def slow(emit):
        started.set()
        await asyncio.sleep(3600)

    job = jobs.start("slow", slow)
    await started.wait()
    assert jobs.cancel(job.id)
    events = [e async for e in jobs.stream(job.id)]
    assert job.status == "cancelled" and events[-1]["status"] == "cancelled"
    assert not jobs.cancel(job.id) and jobs.get("nope") is None


async def test_eviction_keeps_running_jobs():
    jobs = JobManager(max_jobs=2)

    async def quick(emit):
        return 1

    first = jobs.start("q", quick)
    await asyncio.sleep(0.01)
    jobs.start("q", quick)
    await asyncio.sleep(0.01)
    jobs.start("q", quick)
    assert jobs.get(first.id) is None and len(jobs.jobs) == 2
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/test_cases.py tests/test_jobs.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

`backend/btcintel/cases/__init__.py` and `backend/btcintel/jobs/__init__.py`: empty.

`backend/btcintel/cases/store.py`:
```python
"""Saved investigations: graph state (opaque JSON from the UI), notes and a watchlist."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from btcintel.chain.validate import normalize_address

MAX_GRAPH_BYTES = 10_000_000


class Case(BaseModel):
    id: str
    name: str
    notes: str
    graph: dict[str, Any]
    created_at: float
    updated_at: float
    watch: list[str] = []


class CaseSummary(BaseModel):
    id: str
    name: str
    created_at: float
    updated_at: float
    nodes: int


def _graph_json(graph: dict[str, Any]) -> str:
    text = json.dumps(graph, separators=(",", ":"))
    if len(text.encode()) > MAX_GRAPH_BYTES:
        raise ValueError(f"graph too large (limit {MAX_GRAPH_BYTES} bytes)")
    return text


class CaseStore:
    def __init__(self, conn: sqlite3.Connection, clock: Callable[[], float] = time.time) -> None:
        self.conn = conn
        self._clock = clock

    def create(self, name: str, notes: str = "", graph: dict[str, Any] | None = None) -> Case:
        now = self._clock()
        case_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO cases (id, name, notes, graph, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, name, notes, _graph_json(graph or {}), now, now),
        )
        return self.get(case_id)  # type: ignore[return-value]

    def get(self, case_id: str) -> Case | None:
        r = self.conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if r is None:
            return None
        watch = [w["address"] for w in self.conn.execute(
            "SELECT address FROM case_watch WHERE case_id = ? ORDER BY added_at, address", (case_id,))]
        return Case(id=r["id"], name=r["name"], notes=r["notes"], graph=json.loads(r["graph"]),
                    created_at=r["created_at"], updated_at=r["updated_at"], watch=watch)

    def list(self) -> list[CaseSummary]:
        rows = self.conn.execute("SELECT * FROM cases ORDER BY updated_at DESC, id")
        return [CaseSummary(id=r["id"], name=r["name"], created_at=r["created_at"],
                            updated_at=r["updated_at"], nodes=len(json.loads(r["graph"]).get("nodes", [])))
                for r in rows]

    def update(self, case_id: str, *, name: str | None = None, notes: str | None = None,
               graph: dict[str, Any] | None = None) -> Case | None:
        if self.get(case_id) is None:
            return None
        self.conn.execute(
            "UPDATE cases SET name = COALESCE(?, name), notes = COALESCE(?, notes), "
            "graph = COALESCE(?, graph), updated_at = ? WHERE id = ?",
            (name, notes, None if graph is None else _graph_json(graph), self._clock(), case_id),
        )
        return self.get(case_id)

    def delete(self, case_id: str) -> bool:
        return self.conn.execute("DELETE FROM cases WHERE id = ?", (case_id,)).rowcount > 0

    def watch(self, case_id: str, address: str) -> bool:
        if self.get(case_id) is None:
            return False
        self.conn.execute(
            "INSERT OR IGNORE INTO case_watch (case_id, address, added_at) VALUES (?, ?, ?)",
            (case_id, normalize_address(address), self._clock()),
        )
        return True

    def unwatch(self, case_id: str, address: str) -> bool:
        return self.conn.execute(
            "DELETE FROM case_watch WHERE case_id = ? AND address = ?",
            (case_id, normalize_address(address)),
        ).rowcount > 0
```

`backend/btcintel/jobs/manager.py`:
```python
"""In-process background jobs with replayable event streams (for SSE)."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

Emit = Callable[[dict[str, Any]], None]


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    task: asyncio.Task[Any] | None = None
    changed: asyncio.Event = field(default_factory=asyncio.Event)

    def push(self, event: dict[str, Any]) -> None:
        self.events.append({"seq": len(self.events), **event})
        self.changed.set()


class JobManager:
    def __init__(self, max_jobs: int = 200) -> None:
        self.max_jobs = max_jobs
        self.jobs: OrderedDict[str, Job] = OrderedDict()

    def start(self, kind: str, fn: Callable[[Emit], Awaitable[Any]]) -> Job:
        job = Job(id=uuid.uuid4().hex, kind=kind)

        async def runner() -> None:
            try:
                job.result = await fn(job.push)
                job.status = "done"
            except asyncio.CancelledError:
                job.status = "cancelled"
            except Exception as e:  # noqa: BLE001 - surfaced to the client
                job.status = "error"
                job.error = f"{type(e).__name__}: {e}"
            finally:
                job.push({"type": "status", "status": job.status, "error": job.error})

        job.task = asyncio.get_running_loop().create_task(runner())
        self.jobs[job.id] = job
        self._evict()
        return job

    def _evict(self) -> None:
        for jid in list(self.jobs):
            if len(self.jobs) <= self.max_jobs:
                break
            if self.jobs[jid].status != "running":
                del self.jobs[jid]

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job is None or job.task is None or job.task.done():
            return False
        job.task.cancel()
        return True

    async def stream(self, job_id: str, start: int = 0) -> AsyncIterator[dict[str, Any]]:
        job = self.jobs[job_id]
        i = start
        while True:
            while i < len(job.events):
                yield job.events[i]
                i += 1
            if job.status != "running":  # the final status event is pushed in the same step
                return
            job.changed.clear()
            if i < len(job.events):
                continue
            await job.changed.wait()
```

- [ ] **Step 3: Run tests, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/test_cases.py tests/test_jobs.py -v && uv run ruff check .`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/cases backend/btcintel/jobs backend/tests/test_cases.py backend/tests/test_jobs.py
git commit -m "feat: case files with watchlists and background job manager with event streams

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: Runtime wiring, HTTP API and CLI (serve, tx, trace, cluster)

**Files:**
- Create: `backend/btcintel/runtime.py`, `backend/btcintel/api/__init__.py`, `backend/btcintel/api/app.py`, `backend/btcintel/api/deps.py`, `backend/btcintel/api/routes_chain.py`, `backend/btcintel/api/routes_trace.py`, `backend/btcintel/api/routes_cluster.py`, `backend/btcintel/api/routes_tags.py`, `backend/btcintel/api/routes_cases.py`, `backend/btcintel/api/routes_kb.py`
- Modify: `backend/btcintel/cli.py`
- Test: `backend/tests/api/conftest.py`, `backend/tests/api/test_api.py`, `backend/tests/test_cli_chain.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `AppState(settings, chain, conn, tags, uf, cases, jobs, catalog, taxonomy)`, with `.labels(stop_categories=None) -> LabelLookup` and `.context() -> Context`
  - `open_runtime(settings, chain=None)`, an async context manager yielding `AppState`. It builds a `ChainClient` from `settings.backends` (with the proxy) when no chain is given, and closes everything on exit.
  - `create_app(settings=None, *, chain=None) -> FastAPI`, which serves `web/dist` at `/` when it exists
  - The CLI adds `btcintel serve [--host] [--port]`, `btcintel tx TXID`, `btcintel trace SEED [--backward] [--hops N] [--model M] [--peel] [--max-calls N] [--through-coinjoin]` and `btcintel cluster ADDRESS [--max-addresses N] [--max-calls N]`

**API contract** (Plan 3 builds against this; every path is under `/api`):

| Method, path | Request | Response |
|---|---|---|
| GET `/health` | — | `{status, version}` |
| GET `/search?q=` | — | `{kind: "txid"\|"outpoint"\|"address"\|"text", query, tags?: Tag[]}` |
| GET `/tx/{txid}?price=0\|1` | — | `{tx: Tx, findings: Finding[], flags: string[], addresses: {addr: AddressInfoDict}, price_usd: number\|null}` |
| GET `/tx/{txid}/outspends` | — | `Outspend[]` |
| GET `/address/{address}` | — | `{stats: AddressStats, info: AddressInfoDict, cluster: ClusterMeta\|null}` |
| GET `/address/{address}/txs?after=` | — | `{txs: TxSummary[], next: txid\|null}`, where `TxSummary = {txid, block_height, block_time, fee, n_in, n_out, value_out, delta, flags}` |
| POST `/trace` | `{seed: TraceSeed, policy?: TracePolicy}` | 202 `{job_id}` |
| POST `/peel` | `{txid, max_steps?}` | `PeelChain` |
| GET `/jobs/{id}` | — | `{id, kind, status, error, events, result}` (result only when done) |
| GET `/jobs/{id}/events?since=` | — | `text/event-stream` of `data: {seq, type, …}` events |
| DELETE `/jobs/{id}` | — | `{cancelled}` |
| GET `/cluster/{address}?limit=` | — | `{root: null, address}` or `{root, meta, members, tags, conflicts, links}` |
| POST `/cluster/{address}/expand` | `ExpandPolicy?` | 202 `{job_id}` |
| GET `/tags?address=` | — | `Tag[]` |
| GET `/tags/search?q=&limit=` | — | `Tag[]` |
| GET `/tags/packs` | — | `[{pack, count}]` |
| POST `/tags` | `{address, label, category, abuse?, actor?, source?, confidence?}` | 201 `Tag` |
| DELETE `/tags/{id}` | — | 204 |
| GET `/tags/export?pack=user` | — | YAML |
| POST `/tags/import` | `{pack, yaml}` | `{tags, warnings}` |
| GET `/cases` | — | `CaseSummary[]` |
| POST `/cases` | `{name, notes?, graph?}` | 201 `Case` |
| GET/PUT/DELETE `/cases/{id}` | PUT body: `{name?, notes?, graph?}` | `Case` / 204 |
| POST `/cases/{id}/watch` | `{address}` | `Case` |
| DELETE `/cases/{id}/watch/{address}` | — | `Case` |
| GET `/kb/{collection}` | collection ∈ heuristics, techniques, incidents, categories, references | catalog entries |
| GET `/kb-page?path=` | — | `{path, markdown}` |

Errors:

| Condition | Status and body |
|---|---|
| Invalid txid or address | 400 `{detail}` |
| Unknown object | 404 |
| Invalid body | 422 |
| Backend failure | 502 `{detail, incomplete: true}` |
| Budget exhausted | 503 `{detail, incomplete: true}` |

- [ ] **Step 1: Write the API test fixture and the failing tests**

`backend/tests/api/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient

from btcintel.api.app import create_app
from btcintel.config import load_settings
from tests.fakes import FakeChain
from tests.scenario import build_scenario, scenario_tags


@pytest.fixture
def scenario():
    return build_scenario()


@pytest.fixture
def make_client(tmp_path, scenario):
    clients = []

    def _make(chain=None) -> TestClient:
        settings = load_settings({"BTCINTEL_DATA_DIR": str(tmp_path / f"data{len(clients)}")})
        app = create_app(settings, chain=chain or FakeChain(scenario.txs))
        client = TestClient(app)
        client.__enter__()
        app.state.rt.tags.add_many(scenario_tags())
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    return make_client()


def wait_job(client, job_id, timeout=5.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")
```

`backend/tests/api/test_api.py`:
```python
from btcintel import __version__
from tests.api.conftest import wait_job
from tests.builders import ADDR
from tests.fakes import FakeChain
from tests.scenario import EX, H1, V


def test_health_and_search(client, scenario):
    assert client.get("/api/health").json() == {"status": "ok", "version": __version__}
    assert client.get("/api/search", params={"q": scenario.theft.txid.upper()}).json() == {
        "kind": "txid", "query": scenario.theft.txid}
    body = client.get("/api/search", params={"q": "example exchange"}).json()
    assert body["kind"] == "text" and body["tags"][0]["address"] == EX


def test_tx_endpoint(client, scenario):
    body = client.get(f"/api/tx/{scenario.theft.txid}").json()
    assert body["tx"]["txid"] == scenario.theft.txid and body["price_usd"] is None
    assert any(f["heuristic"] == "H-FP" for f in body["findings"])
    assert set(body["addresses"]) >= {V, H1} and body["flags"] == []
    assert client.get(f"/api/tx/{scenario.theft.txid}/outspends").json()[0]["spent"] is True


def test_invalid_ids_return_400(client):
    assert client.get("/api/tx/xyz").status_code == 400
    assert client.get("/api/address/notanaddress").status_code == 400
    assert client.get("/api/address/" + ADDR[0] + "/txs", params={"after": "zz"}).status_code == 400


def test_unknown_tx_is_404(client):
    assert client.get("/api/tx/" + "ab" * 32).status_code == 404


def test_backend_failure_is_502(make_client, scenario):
    c = make_client(FakeChain(scenario.txs, fail_on={scenario.t1.txid}))
    r = c.get(f"/api/tx/{scenario.t1.txid}")
    assert r.status_code == 502 and r.json()["incomplete"] is True


def test_uppercase_bech32_address_is_normalised(client):
    body = client.get(f"/api/address/{H1.upper()}").json()
    assert body["stats"]["address"] == H1 and body["info"]["address"] == H1
    page = client.get(f"/api/address/{H1}/txs").json()
    assert page["txs"][0]["delta"] == 600_000 and page["next"]


def test_trace_job_and_event_stream(client, scenario):
    r = client.post("/api/trace", json={"seed": {"txid": scenario.theft.txid}, "policy": {"max_hops": 4}})
    assert r.status_code == 202
    job = wait_job(client, r.json()["job_id"])
    assert job["status"] == "done" and not job["result"]["incomplete"]
    assert {s["reason"] for s in job["result"]["stops"]} >= {"labeled", "unspent"}
    with client.stream("GET", f"/api/jobs/{job['id']}/events") as stream:
        lines = [line for line in stream.iter_lines() if line.startswith("data: ")]
    assert '"type": "done"' in lines[-2] and '"status": "done"' in lines[-1]
    assert client.post("/api/trace", json={"seed": {"txid": "zz"}}).status_code == 422
    assert client.get("/api/jobs/nope").status_code == 404


def test_peel_endpoint(client, scenario):
    body = client.post("/api/peel", json={"txid": scenario.t1.txid}).json()
    assert body["start_txid"] == scenario.t1.txid and body["end_reason"] in {"unspent", "not_peel_shaped", "labeled"}


def test_cluster_expand_and_get(client, scenario):
    job = wait_job(client, client.post(f"/api/cluster/{V}/expand", json={"max_calls": 50}).json()["job_id"])
    assert job["status"] == "done" and job["result"]["root"] == V
    body = client.get(f"/api/cluster/{V}").json()
    assert body["root"] == V and V in body["members"]
    assert client.get(f"/api/cluster/{ADDR[14]}").json() == {"root": None, "address": ADDR[14]}


def test_tags_crud_export_import(client):
    r = client.post("/api/tags", json={"address": ADDR[6].upper(), "label": "Suspect", "category": "perpetrator",
                                       "abuse": "theft"})
    assert r.status_code == 201 and r.json()["address"] == ADDR[6] and r.json()["pack"] == "user"
    assert client.post("/api/tags", json={"address": ADDR[6], "label": "x", "category": "nope"}).status_code == 400
    assert client.get("/api/tags", params={"address": ADDR[6]}).json()[0]["label"] == "Suspect"
    exported = client.get("/api/tags/export", params={"pack": "user"}).text
    assert "Suspect" in exported
    imported = client.post("/api/tags/import", json={"pack": "roundtrip", "yaml": exported}).json()
    assert imported["tags"] == 1
    assert client.post("/api/tags/import", json={"pack": "bad", "yaml": "tags: [oops"}).status_code == 400
    assert {"pack": "roundtrip", "count": 1} in client.get("/api/tags/packs").json()
    tag_id = r.json()["id"]
    assert client.delete(f"/api/tags/{tag_id}").status_code == 204
    assert client.delete(f"/api/tags/{tag_id}").status_code == 404


def test_cases_crud(client):
    case = client.post("/api/cases", json={"name": "Investigation"}).json()
    assert client.get("/api/cases").json()[0]["id"] == case["id"]
    updated = client.put(f"/api/cases/{case['id']}", json={"notes": "n", "graph": {"nodes": [1]}}).json()
    assert updated["notes"] == "n" and updated["graph"] == {"nodes": [1]}
    watched = client.post(f"/api/cases/{case['id']}/watch", json={"address": ADDR[1]}).json()
    assert watched["watch"] == [ADDR[1]]
    assert client.delete(f"/api/cases/{case['id']}/watch/{ADDR[1]}").json()["watch"] == []
    assert client.post(f"/api/cases/{case['id']}/watch", json={"address": "bad"}).status_code == 400
    assert client.delete(f"/api/cases/{case['id']}").status_code == 204
    assert client.get(f"/api/cases/{case['id']}").status_code == 404


def test_kb_endpoints(client):
    heuristics = client.get("/api/kb/heuristics").json()
    assert any(h["id"] == "H-CIOH" for h in heuristics)
    assert client.get("/api/kb/nope").status_code == 404
    page = client.get("/api/kb-page", params={"path": "heuristics/h-cioh.md"}).json()
    assert page["markdown"].startswith("# H-CIOH")


def test_kb_page_rejects_traversal(client):
    assert client.get("/api/kb-page", params={"path": "../../README.md"}).status_code == 400
    assert client.get("/api/kb-page", params={"path": "heuristics/missing.md"}).status_code == 404
    assert client.get("/api/kb-page", params={"path": "../../backend/pyproject.toml"}).status_code == 400
```

`backend/tests/test_cli_chain.py`:
```python
import json
from pathlib import Path

import httpx
import respx

from btcintel.cli import main

FIX = Path(__file__).resolve().parent / "fixtures" / "esplora"
TXID = "c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c"


@respx.mock(assert_all_called=False)
def test_tx_command_prints_findings(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("BTCINTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("BTCINTEL_BACKENDS", "t=https://esplora.test/api@100")
    respx.get("https://esplora.test/api/blocks/tip/height").mock(return_value=httpx.Response(200, text="900100"))
    respx.get(f"https://esplora.test/api/tx/{TXID}").mock(
        return_value=httpx.Response(200, json=json.loads((FIX / "tx_c5908e04.json").read_text())))
    assert main(["tx", TXID]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["txid"] == TXID and any(f["heuristic"] == "H-FP" for f in out["findings"])


def test_tx_command_rejects_bad_txid(capsys):
    assert main(["tx", "nope"]) == 2
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/api tests/test_cli_chain.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement the runtime**

`backend/btcintel/runtime.py`:
```python
"""Wire settings → chain source, intel database, stores, catalog. Shared by the API and the CLI."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from btcintel import __version__
from btcintel.cases.store import CaseStore
from btcintel.catalog.loader import load_catalog
from btcintel.catalog.schema import Catalog
from btcintel.chain.cache import Cache
from btcintel.chain.client import ChainClient
from btcintel.chain.esplora import EsploraBackend
from btcintel.chain.source import ChainSource
from btcintel.cluster.unionfind import UnionFind
from btcintel.config import Settings
from btcintel.db import open_intel_db
from btcintel.heuristics.base import Context
from btcintel.jobs.manager import JobManager
from btcintel.labels.lookup import LabelLookup
from btcintel.labels.store import TagStore
from btcintel.labels.taxonomy import Taxonomy


@dataclass
class AppState:
    settings: Settings
    chain: ChainSource
    conn: sqlite3.Connection
    tags: TagStore
    uf: UnionFind
    cases: CaseStore
    jobs: JobManager
    catalog: Catalog
    taxonomy: Taxonomy

    def labels(self, stop_categories: Iterable[str] | None = None) -> LabelLookup:
        return LabelLookup(self.tags, self.taxonomy, self.uf, stop_categories)

    def context(self) -> Context:
        return Context(chain=self.chain, coinbase_rules=self.tags.coinbase_rules())


@asynccontextmanager
async def open_runtime(settings: Settings, chain: ChainSource | None = None) -> AsyncIterator[AppState]:
    http: httpx.AsyncClient | None = None
    cache: Cache | None = None
    if chain is None:
        http = httpx.AsyncClient(
            proxy=settings.proxy, timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=True,
            headers={"User-Agent": f"btc-intel/{__version__}"},
        )
        cache = Cache(settings.cache_path)
        chain = ChainClient([EsploraBackend(b, http) for b in settings.backends], cache)
    conn = open_intel_db(settings.intel_path)
    catalog = load_catalog(settings.catalog_dir)
    try:
        yield AppState(settings=settings, chain=chain, conn=conn, tags=TagStore(conn), uf=UnionFind(conn),
                       cases=CaseStore(conn), jobs=JobManager(), catalog=catalog,
                       taxonomy=Taxonomy.from_catalog(catalog))
    finally:
        if http is not None:
            await http.aclose()
        if cache is not None:
            cache.close()
        conn.close()
```

- [ ] **Step 3: Implement the API**

`backend/btcintel/api/__init__.py`: empty.

`backend/btcintel/api/deps.py`:
```python
"""Request-scoped helpers: runtime access and identifier validation."""

from __future__ import annotations

from fastapi import HTTPException, Request

from btcintel.chain.validate import is_address, is_txid, normalize_address
from btcintel.runtime import AppState


def rt(request: Request) -> AppState:
    return request.app.state.rt


def valid_txid(txid: str) -> str:
    if not is_txid(txid):
        raise HTTPException(status_code=400, detail="invalid txid")
    return txid.lower()


def valid_address(address: str) -> str:
    if not is_address(address):
        raise HTTPException(status_code=400, detail="invalid Bitcoin mainnet address")
    return normalize_address(address)
```

`backend/btcintel/api/routes_chain.py`:
```python
"""Chain lookups: search, transactions (with findings), addresses."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from btcintel import __version__
from btcintel.api.deps import rt, valid_address, valid_txid
from btcintel.chain.budget import CallBudget, budget_scope
from btcintel.chain.models import Tx
from btcintel.chain.validate import classify_query
from btcintel.heuristics.base import analyze_tx
from btcintel.heuristics.flags import tx_flags
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


def tx_summary(tx: Tx, address: str | None = None) -> dict[str, Any]:
    delta = None
    if address is not None:
        delta = (sum(o.value for o in tx.vout if o.address == address)
                 - sum(i.value for i in tx.vin if i.address == address))
    return {"txid": tx.txid, "block_height": tx.status.block_height, "block_time": tx.status.block_time,
            "fee": tx.fee, "n_in": len(tx.vin), "n_out": len(tx.vout), "value_out": tx.output_value,
            "delta": delta, "flags": tx_flags(tx)}


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/search")
async def search(q: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    kind, value = classify_query(q)
    if kind == "text":
        return {"kind": kind, "query": value, "tags": [t.model_dump() for t in s.tags.search(value)]}
    return {"kind": kind, "query": value}


@router.get("/tx/{txid}")
async def get_tx(txid: str, price: bool = False, s: AppState = Depends(rt)) -> dict[str, Any]:
    tx = await s.chain.get_tx(valid_txid(txid))
    with budget_scope(CallBudget(40)):
        findings = await analyze_tx(tx, s.context())
    labels = s.labels()
    addresses = dict.fromkeys([*tx.input_addresses(), *tx.output_addresses()])
    price_usd = None
    if price and tx.status.block_time:
        price_usd = await s.chain.get_price_usd(tx.status.block_time)
    return {"tx": tx.model_dump(), "findings": [f.model_dump() for f in findings], "flags": tx_flags(tx),
            "addresses": {a: labels.lookup(a).to_dict() for a in addresses}, "price_usd": price_usd}


@router.get("/tx/{txid}/outspends")
async def get_outspends(txid: str, s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [o.model_dump() for o in await s.chain.get_outspends(valid_txid(txid))]


@router.get("/address/{address}")
async def get_address(address: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    stats = await s.chain.get_address(address)
    info = s.labels().lookup(address)
    meta = s.uf.meta(info.cluster) if info.cluster else None
    return {"stats": stats.model_dump(), "info": info.to_dict(),
            "cluster": meta.model_dump() if meta else None}


@router.get("/address/{address}/txs")
async def get_address_txs(address: str, after: str | None = None, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    page = await s.chain.get_address_txs(address, valid_txid(after) if after is not None else None)
    confirmed = [t for t in page if t.status.confirmed]
    return {"txs": [tx_summary(t, address) for t in page], "next": confirmed[-1].txid if confirmed else None}
```

`backend/btcintel/api/routes_trace.py`:
```python
"""Tracing jobs, peel-chain following, job status and event streams."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from btcintel.api.deps import rt, valid_txid
from btcintel.chain.budget import CallBudget, budget_scope
from btcintel.runtime import AppState
from btcintel.trace.engine import TracePolicy, TraceSeed, trace
from btcintel.trace.peel import follow_peel_chain

router = APIRouter(prefix="/api")


class TraceRequest(BaseModel):
    seed: TraceSeed
    policy: TracePolicy = TracePolicy()


class PeelRequest(BaseModel):
    txid: str
    max_steps: int = Field(50, ge=1, le=500)


@router.post("/trace", status_code=202)
async def start_trace(req: TraceRequest, s: AppState = Depends(rt)) -> dict[str, str]:
    labels = s.labels(req.policy.stop_categories)

    async def run(emit):
        return (await trace(req.seed, req.policy, chain=s.chain, labels=labels, emit=emit)).model_dump()

    return {"job_id": s.jobs.start("trace", run).id}


@router.post("/peel")
async def peel(req: PeelRequest, s: AppState = Depends(rt)) -> dict[str, Any]:
    txid = valid_txid(req.txid)
    with budget_scope(CallBudget(req.max_steps * 2 + 10)):
        result = await follow_peel_chain(txid, s.chain, s.labels(), max_steps=req.max_steps)
    return result.model_dump()


def _job_or_404(s: AppState, job_id: str):
    job = s.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    job = _job_or_404(s, job_id)
    return {"id": job.id, "kind": job.kind, "status": job.status, "error": job.error,
            "events": len(job.events), "result": job.result if job.status == "done" else None}


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, since: int = 0, s: AppState = Depends(rt)):
    _job_or_404(s, job_id)

    async def gen():
        async for event in s.jobs.stream(job_id, start=since):
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str, s: AppState = Depends(rt)) -> dict[str, bool]:
    _job_or_404(s, job_id)
    return {"cancelled": s.jobs.cancel(job_id)}
```

`backend/btcintel/api/routes_cluster.py`:
```python
"""Cluster inspection and expansion jobs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from btcintel.api.deps import rt, valid_address
from btcintel.cluster.expand import ExpandPolicy, cluster_conflicts, cluster_tags, expand_cluster
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


@router.get("/cluster/{address}")
async def get_cluster(address: str, limit: int = Query(500, ge=1, le=10_000),
                      s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    root = s.uf.root_of(address)
    if root is None:
        return {"root": None, "address": address}
    meta = s.uf.meta(root)
    return {"root": root, "meta": meta.model_dump() if meta else None, "members": s.uf.members(root, limit),
            "tags": [t.model_dump() for t in cluster_tags(root, s.uf, s.tags)[:200]],
            "conflicts": [c.model_dump() for c in cluster_conflicts(root, s.uf, s.tags)],
            "links": s.uf.links(root)}


@router.post("/cluster/{address}/expand", status_code=202)
async def expand(address: str, policy: ExpandPolicy | None = None, s: AppState = Depends(rt)) -> dict[str, str]:
    address = valid_address(address)

    async def run(emit):
        result = await expand_cluster(address, s.chain, s.uf, s.tags, policy or ExpandPolicy(), progress=emit)
        return result.model_dump()

    return {"job_id": s.jobs.start("cluster", run).id}
```

`backend/btcintel/api/routes_tags.py`:
```python
"""Attribution tags: lookup, search, analyst tags, TagPack export/import."""

from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from btcintel.api.deps import rt, valid_address
from btcintel.labels.importers import import_tagpack_text
from btcintel.labels.store import CONFIDENCE_LEVELS, Tag
from btcintel.labels.tagpack import export_tagpack
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


class NewTag(BaseModel):
    address: str
    label: str = Field(min_length=1, max_length=200)
    category: str
    abuse: str | None = None
    actor: str | None = Field(None, max_length=200)
    source: str = Field("analyst", max_length=500)
    confidence: str = "forensic_investigation"


class ImportRequest(BaseModel):
    pack: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")
    yaml: str = Field(max_length=20_000_000)


@router.get("/tags")
async def tags_for_address(address: str, s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [t.model_dump() for t in s.tags.for_address(valid_address(address))]


@router.get("/tags/search")
async def search_tags(q: str, limit: int = Query(50, ge=1, le=500), s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [t.model_dump() for t in s.tags.search(q, limit)]


@router.get("/tags/packs")
async def packs(s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [{"pack": p, "count": n} for p, n in s.tags.packs()]


@router.post("/tags", status_code=201)
async def add_tag(body: NewTag, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(body.address)
    if body.category not in s.taxonomy.categories:
        raise HTTPException(status_code=400, detail=f"unknown category {body.category!r}")
    if body.abuse is not None and body.abuse not in s.taxonomy.categories:
        raise HTTPException(status_code=400, detail=f"unknown abuse category {body.abuse!r}")
    if body.confidence not in CONFIDENCE_LEVELS:
        raise HTTPException(status_code=400, detail=f"unknown confidence {body.confidence!r}")
    tag = Tag(address=address, label=body.label, category=body.category, abuse=body.abuse, actor=body.actor,
              confidence=body.confidence, source=body.source, pack="user", created_by="analyst")
    stored = s.tags.get(s.tags.add(tag))
    return stored.model_dump() if stored else tag.model_dump()


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: int, s: AppState = Depends(rt)) -> Response:
    if not s.tags.delete(tag_id):
        raise HTTPException(status_code=404, detail="unknown tag")
    return Response(status_code=204)


@router.get("/tags/export", response_class=PlainTextResponse)
async def export(pack: str = "user", s: AppState = Depends(rt)) -> PlainTextResponse:
    text = export_tagpack(s.tags.by_pack(pack), title=f"btc-intel {pack} tags", creator="btc-intel")
    return PlainTextResponse(text, media_type="application/yaml")


@router.post("/tags/import")
async def import_tags(body: ImportRequest, s: AppState = Depends(rt)) -> dict[str, Any]:
    try:
        report = import_tagpack_text(s.tags, s.taxonomy, body.yaml, body.pack)
    except (ValueError, yaml.YAMLError) as e:
        raise HTTPException(status_code=400, detail=f"invalid TagPack: {e}") from e
    return {"tags": report.tags, "warnings": report.warnings[:100]}
```

`backend/btcintel/api/routes_cases.py`:
```python
"""Case files: CRUD and watchlists."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from btcintel.api.deps import rt, valid_address
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")


class CaseBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str = ""
    graph: dict[str, Any] | None = None


class CaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    notes: str | None = None
    graph: dict[str, Any] | None = None


class WatchBody(BaseModel):
    address: str


def _case_or_404(s: AppState, case_id: str):
    case = s.cases.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="unknown case")
    return case


@router.get("/cases")
async def list_cases(s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    return [c.model_dump() for c in s.cases.list()]


@router.post("/cases", status_code=201)
async def create_case(body: CaseBody, s: AppState = Depends(rt)) -> dict[str, Any]:
    try:
        return s.cases.create(body.name, body.notes, body.graph).model_dump()
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e


@router.get("/cases/{case_id}")
async def get_case(case_id: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    return _case_or_404(s, case_id).model_dump()


@router.put("/cases/{case_id}")
async def update_case(case_id: str, body: CaseUpdate, s: AppState = Depends(rt)) -> dict[str, Any]:
    try:
        case = s.cases.update(case_id, name=body.name, notes=body.notes, graph=body.graph)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    if case is None:
        raise HTTPException(status_code=404, detail="unknown case")
    return case.model_dump()


@router.delete("/cases/{case_id}", status_code=204)
async def delete_case(case_id: str, s: AppState = Depends(rt)) -> Response:
    if not s.cases.delete(case_id):
        raise HTTPException(status_code=404, detail="unknown case")
    return Response(status_code=204)


@router.post("/cases/{case_id}/watch")
async def watch(case_id: str, body: WatchBody, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(body.address)
    _case_or_404(s, case_id)
    s.cases.watch(case_id, address)
    return _case_or_404(s, case_id).model_dump()


@router.delete("/cases/{case_id}/watch/{address}")
async def unwatch(case_id: str, address: str, s: AppState = Depends(rt)) -> dict[str, Any]:
    address = valid_address(address)
    _case_or_404(s, case_id)
    s.cases.unwatch(case_id, address)
    return _case_or_404(s, case_id).model_dump()
```

`backend/btcintel/api/routes_kb.py`:
```python
"""Knowledge base: catalog collections and Markdown pages (confined to docs/kb)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from btcintel.api.deps import rt
from btcintel.runtime import AppState

router = APIRouter(prefix="/api")
COLLECTIONS = ("heuristics", "techniques", "incidents", "categories", "references")


@router.get("/kb/{collection}")
async def kb_collection(collection: str, s: AppState = Depends(rt)) -> list[dict[str, Any]]:
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail="unknown collection")
    return [e.model_dump() for e in getattr(s.catalog, collection)]


@router.get("/kb-page")
async def kb_page(path: str, s: AppState = Depends(rt)) -> dict[str, str]:
    root = s.settings.kb_dir.resolve()
    page = (root / path).resolve()
    if not page.is_relative_to(root) or page.suffix != ".md":
        raise HTTPException(status_code=400, detail="path must be a .md file inside docs/kb")
    if not page.is_file():
        raise HTTPException(status_code=404, detail="no such page")
    return {"path": page.relative_to(root).as_posix(), "markdown": page.read_text(encoding="utf-8")}
```

`backend/btcintel/api/app.py`:
```python
"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from btcintel import __version__
from btcintel.api import routes_cases, routes_chain, routes_cluster, routes_kb, routes_tags, routes_trace
from btcintel.chain.budget import BudgetExceeded
from btcintel.chain.errors import NotFound, SourceError
from btcintel.chain.source import ChainSource
from btcintel.config import Settings, load_settings
from btcintel.paths import REPO_ROOT
from btcintel.runtime import open_runtime


def create_app(settings: Settings | None = None, *, chain: ChainSource | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_runtime(settings, chain) as state:
            app.state.rt = state
            yield

    app = FastAPI(title="btc-intel", version=__version__, lifespan=lifespan)
    for module in (routes_chain, routes_trace, routes_cluster, routes_tags, routes_cases, routes_kb):
        app.include_router(module.router)

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(SourceError)
    async def source_error(request: Request, exc: SourceError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc), "incomplete": True})

    @app.exception_handler(BudgetExceeded)
    async def budget(request: Request, exc: BudgetExceeded) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc), "incomplete": True})

    dist = REPO_ROOT / "web" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app
```

- [ ] **Step 4: Add the CLI commands**

In `backend/btcintel/cli.py` add these imports:
```python
import asyncio
import json

from btcintel.chain.errors import ChainError
from btcintel.chain.validate import classify_query, is_address, is_txid
```
Add these handlers:
```python
def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from btcintel.api.app import create_app

    settings = load_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: binding to a non-loopback address exposes an unauthenticated API", file=sys.stderr)
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info")
    return 0


def _cmd_tx(args: argparse.Namespace) -> int:
    if not is_txid(args.txid):
        print("invalid txid", file=sys.stderr)
        return 2
    return asyncio.run(_tx(args.txid.lower()))


async def _tx(txid: str) -> int:
    from btcintel.heuristics.base import analyze_tx
    from btcintel.heuristics.flags import tx_flags
    from btcintel.runtime import open_runtime

    async with open_runtime(load_settings()) as rt:
        try:
            tx = await rt.chain.get_tx(txid)
            findings = await analyze_tx(tx, rt.context())
        except ChainError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(json.dumps({"txid": tx.txid, "flags": tx_flags(tx),
                          "findings": [f.model_dump() for f in findings]}, indent=2))
    return 0


def _cmd_trace(args: argparse.Namespace) -> int:
    kind, value = classify_query(args.seed)
    if kind not in ("txid", "outpoint", "address"):
        print("seed must be a txid, txid:vout or address", file=sys.stderr)
        return 2
    return asyncio.run(_trace(kind, value, args))


async def _trace(kind: str, value: str, args: argparse.Namespace) -> int:
    from btcintel.runtime import open_runtime
    from btcintel.trace.engine import TracePolicy, TraceSeed, trace

    if kind == "outpoint":
        txid, vout = value.split(":")
        seed = TraceSeed(txid=txid, vout=int(vout))
    elif kind == "txid":
        seed = TraceSeed(txid=value)
    else:
        seed = TraceSeed(address=value)
    policy = TracePolicy(direction="backward" if args.backward else "forward", max_hops=args.hops,
                         taint_model=args.model, peel_mode=args.peel, max_calls=args.max_calls,
                         coinjoin="through" if args.through_coinjoin else "stop")
    async with open_runtime(load_settings()) as rt:
        try:
            result = await trace(seed, policy, chain=rt.chain, labels=rt.labels())
        except ChainError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    order = {"labeled": 0, "coinjoin": 1, "unspent": 2}
    stops = sorted(result.stops, key=lambda st: (order.get(st.reason, 9), -st.taint))
    print(json.dumps({
        "txs": result.txs_expanded, "addresses": sum(n.kind == "address" for n in result.nodes),
        "incomplete": result.incomplete, "reason": result.reason, "calls_used": result.calls_used,
        "stops": [st.model_dump() for st in stops[:50]],
    }, indent=2))
    return 0


def _cmd_cluster(args: argparse.Namespace) -> int:
    if not is_address(args.address):
        print("invalid address", file=sys.stderr)
        return 2
    return asyncio.run(_cluster(args))


async def _cluster(args: argparse.Namespace) -> int:
    from btcintel.cluster.expand import ExpandPolicy, expand_cluster
    from btcintel.runtime import open_runtime

    async with open_runtime(load_settings()) as rt:
        result = await expand_cluster(args.address, rt.chain, rt.uf, rt.tags,
                                      ExpandPolicy(max_addresses=args.max_addresses, max_calls=args.max_calls))
    print(json.dumps(result.model_dump(), indent=2))
    return 0


COMMANDS.update({"serve": _cmd_serve, "tx": _cmd_tx, "trace": _cmd_trace, "cluster": _cmd_cluster})
```
In `_build_parser()`:
```python
    sv = sub.add_parser("serve", help="run the local API (and web UI if built)")
    sv.add_argument("--host")
    sv.add_argument("--port", type=int)
    txp = sub.add_parser("tx", help="analyze one transaction")
    txp.add_argument("txid")
    tr = sub.add_parser("trace", help="trace funds from a txid, txid:vout or address")
    tr.add_argument("seed")
    tr.add_argument("--backward", action="store_true")
    tr.add_argument("--hops", type=int, default=6)
    tr.add_argument("--model", choices=["haircut", "fifo", "poison"], default="haircut")
    tr.add_argument("--peel", action="store_true", help="follow only the remainder (peel chains)")
    tr.add_argument("--max-calls", type=int, default=600)
    tr.add_argument("--through-coinjoin", action="store_true")
    cl = sub.add_parser("cluster", help="expand the CIOH cluster of an address")
    cl.add_argument("address")
    cl.add_argument("--max-addresses", type=int, default=2000)
    cl.add_argument("--max-calls", type=int, default=400)
```

- [ ] **Step 5: Run the full suite, then commit**

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest -v && uv run ruff check .`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add backend/btcintel/runtime.py backend/btcintel/api backend/btcintel/cli.py backend/tests/api backend/tests/test_cli_chain.py
git commit -m "feat(api): FastAPI server (chain, trace jobs + SSE, clusters, tags, cases, KB) and CLI commands

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Live smoke test (manual, network)**

```bash
cd /home/fancybear/btc-intel/backend
uv run btcintel tx c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c | head -30
uv run btcintel serve &
sleep 3
curl -s localhost:8765/api/health
curl -s "localhost:8765/api/tx/c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c?price=1" | python3 -m json.tool | head -40
kill %1
```
Expected: findings include H-FP, the health check returns `{"status":"ok",…}`, and `price_usd` is about 100k (block 900000 was mined in June 2025).

---

### Task 18: Real-mainnet regression fixtures and incident dogfood

**Files:**
- Create: `backend/scripts/record_fixtures.py`, `backend/tests/fixtures/real/**` (recorded), `backend/tests/heuristics/test_real_coinjoins.py`, `backend/tests/test_dogfood.py`
- Modify: `docs/kb/incidents/*.md` (add the dogfood results under "Detection in btc-intel")

**Interfaces:**
- Consumes: `parse_tx`, `classify_coinjoin`, `MULTIPARTY_KINDS`, `STRONG_KINDS`, `cioh_addresses`, `open_runtime`, `trace`, `load_catalog`.
- Produces: the committed fixtures `tests/fixtures/real/<kind>/<txid>.json` and `tests/fixtures/real/manifest.json` (`{kind: [{txid, source}]}`), where kind ∈ {wasabi2, whirlpool, whirlpool_tx0, wasabi1, other_coinjoin, ordinary}.

- [ ] **Step 1: Write the recorder**

`backend/scripts/record_fixtures.py`:
```python
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
```

- [ ] **Step 2: Record the fixtures**

Run: `cd /home/fancybear/btc-intel/backend && uv run python scripts/record_fixtures.py`
Expected output, roughly: `{'wasabi2': 12, 'whirlpool': 4, 'whirlpool_tx0': 4, 'wasabi1': 3, 'other_coinjoin': 6, 'ordinary': 40}`.

- [ ] **Step 3: Write the regression tests**

`backend/tests/heuristics/test_real_coinjoins.py`:
```python
import json
from pathlib import Path

import pytest

from btcintel.chain.esplora_parse import parse_tx
from btcintel.heuristics.cioh import cioh_addresses
from btcintel.heuristics.coinjoin import MULTIPARTY_KINDS, STRONG_KINDS, classify_coinjoin

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "real"
MANIFEST = FIX / "manifest.json"
pytestmark = pytest.mark.skipif(not MANIFEST.exists(), reason="run scripts/record_fixtures.py first")


def load(kind: str):
    entries = json.loads(MANIFEST.read_text())[kind]
    return [parse_tx(json.loads((FIX / kind / f"{e['txid']}.json").read_text())) for e in entries]


def kinds(kind: str) -> list[str | None]:
    return [(m.kind if (m := classify_coinjoin(tx)) else None) for tx in load(kind)]


def test_wasabi2_rounds_suppress_cioh_and_are_mostly_identified():
    got = kinds("wasabi2")
    assert all(k in MULTIPARTY_KINDS for k in got), got
    assert got.count("wasabi2") >= 0.8 * len(got), got


@pytest.mark.parametrize("kind", ["whirlpool", "whirlpool_tx0", "wasabi1"])
def test_exact_kinds(kind):
    got = kinds(kind)
    assert got and all(k == kind for k in got), got


def test_tx0s_keep_cioh():
    assert all(cioh_addresses(tx) is not None or len(tx.input_addresses()) < 2 for tx in load("whirlpool_tx0"))


def test_other_coinjoins_are_flagged():
    assert all(k is not None for k in kinds("other_coinjoin"))


def test_ordinary_transactions_are_not_strong_coinjoins():
    got = kinds("ordinary")
    assert not [k for k in got if k in STRONG_KINDS], got
    assert sum(k is not None for k in got) <= 3, got
```

`backend/tests/test_dogfood.py`:
```python
"""Live end-to-end check against published incident seeds (network)."""

import pytest

from btcintel.catalog.loader import load_catalog
from btcintel.config import load_settings
from btcintel.runtime import open_runtime
from btcintel.trace.engine import TracePolicy, TraceSeed, trace

pytestmark = pytest.mark.network


async def test_trace_from_every_incident_seed_completes():
    settings = load_settings()
    cat = load_catalog(settings.catalog_dir)
    seeds = [(inc.id, s) for inc in cat.incidents for s in inc.seeds][:5]
    assert seeds, "Plan 1 Task 7 should have produced incident seeds"
    async with open_runtime(settings) as rt:
        for incident_id, s in seeds:
            seed = TraceSeed(txid=s.value) if s.kind == "tx" else TraceSeed(address=s.value)
            result = await trace(seed, TracePolicy(max_hops=2, max_calls=60, max_txs=30),
                                 chain=rt.chain, labels=rt.labels())
            assert result.txs_expanded >= 1, incident_id
```

Run: `cd /home/fancybear/btc-intel/backend && uv run pytest tests/heuristics/test_real_coinjoins.py -v`
Expected: PASS.

If a sample fails, open that transaction on mempool.space and decide whether the ground-truth label or the rule is wrong:
- A mislabelled sample: remove it from the manifest and write the reason in its `source`.
- A wrong rule: adjust the rule in `coinjoin.py` and re-run every heuristic test.

Never weaken an assertion just to pass.

- [ ] **Step 4: Dogfood published incidents (manual, network)**

```bash
cd /home/fancybear/btc-intel/backend
uv run btcintel import-tags pools && uv run btcintel import-tags ofac && uv run btcintel import-tags graphsense
uv run pytest -m network tests/test_dogfood.py -v
```

Then, for each incident in `catalog/incidents/` that has seeds:
1. Run `uv run btcintel trace <seed> --hops 4 --max-calls 300`. Add `--backward` for seizure or exit addresses, and `--peel` where the KB page says peel chains were used.
2. Compare the hops, amounts and exits with the incident's KB narrative and cited sources.
3. Record the outcome in the incident page's "Detection in btc-intel" section, reproducible from the command line: which labeled exits were reached, where the trace stopped and why, and anything that diverges from the published analysis.

Then run `uv run btcintel catalog check`.

- [ ] **Step 5: Commit**

```bash
cd /home/fancybear/btc-intel
git add backend/scripts backend/tests/fixtures/real backend/tests/heuristics/test_real_coinjoins.py backend/tests/test_dogfood.py docs/kb/incidents
git commit -m "test: real-mainnet CoinJoin regression fixtures and incident dogfood traces

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Plan 2 completion checklist

- [ ] `cd backend && uv run pytest` passes offline, and `uv run pytest -m network` passes.
- [ ] `uv run btcintel catalog check` reports OK. Implemented heuristics: H-FP, H-CJ(+7 children), H-CIOH, H-CHG(+5 signals), H-PEEL, H-MOTIF-FANOUT, H-MOTIF-FANIN, H-XCHAIN, H-COINBASE, H-TAINT.
- [ ] `uv run btcintel serve` answers `/api/health`, and a live `/api/tx/<txid>` returns findings.
- [ ] Incident dogfood results are recorded in `docs/kb/incidents/*.md`.
