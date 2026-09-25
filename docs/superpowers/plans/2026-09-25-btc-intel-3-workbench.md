# btc-intel Plan 3 — Web Graph Workbench (Phase 1 frontend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A browser workbench in the style of Chainalysis Reactor, on top of the Plan 2 API. An analyst can:
- search a txid, address or tag and see an interactive address↔transaction graph, laid out left to right in time
- expand inputs and outputs, run streaming traces, follow peel chains and expand clusters
- inspect heuristic findings, with links to the knowledge base
- tag addresses, save and reload case files, and export PNG, JSON, CSV and Markdown reports
- browse the knowledge base

**Architecture:**
- Vite + React 19 + TypeScript single-page app in `web/`.
- The dev server proxies `/api` to `127.0.0.1:8765`; in production FastAPI serves `web/dist`.
- Graph state is a pure, unit-tested model (`src/graph/model.ts`) held in a zustand store. Side effects live in `src/state/actions.ts`, which calls the typed API client and applies server-sent trace events as reducers.
- Cytoscape.js with the dagre layout renders the model; all graph logic stays out of the canvas component.

**Tech Stack:** Node 20.19, React 19, TypeScript 5.8+, Vite 7, Tailwind CSS 4, TanStack Query 5, zustand 5, Cytoscape.js 3 + cytoscape-dagre, marked + DOMPurify; Vitest 3 + Testing Library + jsdom; Playwright.

**Spec:** `docs/superpowers/specs/2026-09-25-btc-intel-design.md`. **Requires Plan 2 to be complete.** The endpoint shapes used here are exactly the "API contract" table in Plan 2 Task 17.

## Global Constraints

- All web commands run from `/home/fancybear/btc-intel/web`. The Node version is 20.19; the dependency majors below are chosen to support it. If npm reports no matching version, choose the newest release within the same major (`npm view <pkg> versions`).
- The UI talks only to its own origin (`/api/*`). It never contacts third-party services directly, because OPSEC comes from the backend's proxy settings.
- Every value from the API that is rendered as HTML (KB Markdown) goes through DOMPurify. Everything else is rendered as text by React.
- Colours are CSS custom properties on `:root`, redefined under `@media (prefers-color-scheme: dark)`. The graph palette mirrors them in `src/graph/style.ts`.
- Show amounts in BTC with up to 8 decimals (`formatBtc`). Send amounts to the API in satoshis.
- Public-API rate limits make network actions slow (about 1 request/s). The UI must show progress and busy state and never fire unbounded request loops. Expansion helpers cap themselves at 25 transactions per action.
- Every commit ends with the trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Trace events arriving while the user edits the graph (hides nodes, drags them).** Updates must merge, not reset, hidden or positioned nodes. Test: Task 3 `applyJobEvent keeps hidden and positions`.
2. **A partial result (`incomplete`, 502/503) from public-API throttling.** Show a clear partial-result message and keep what was already drawn. Tests: Task 2 `maps error body to ApiError with incomplete`; Task 4 `startTrace records incomplete reason`.
3. **Malicious or odd Markdown/HTML in KB pages or tag labels** (e.g. `<img onerror>`). It must be sanitised or escaped. Test: Task 8 `renderMarkdown strips scripts and event handlers`.
4. **Loading a saved case whose graph JSON is from an older or unknown shape.** Expected: an empty graph with a message, not a crash. Test: Task 3 `fromSaved rejects unknown shapes`.
5. **Very large amounts or zero-value outputs** (OP_RETURN, 0 sats). Formatting and edge widths must stay finite and bounded. Tests: Task 1 `formatBtc` cases; Task 3 `edgeWidth is bounded`.

---

## File Structure

```
web/package.json, tsconfig.json, vite.config.ts, index.html, playwright.config.ts
web/src/main.tsx                 React root + QueryClient
web/src/index.css                Tailwind import + theme tokens (light/dark)
web/src/App.tsx                  layout: header, graph/KB views, sidebar tabs, status bar
web/src/test/setup.ts            jest-dom matchers
web/src/lib/format.ts            formatBtc, shortAddr, shortTxid, formatTime, btcToSats
web/src/lib/route.ts             hash routing (#/graph, #/kb/<path>)
web/src/api/types.ts             TypeScript mirrors of the Plan 2 API contract
web/src/api/client.ts            ApiError, api.* typed fetchers
web/src/api/sse.ts               subscribeJob() over EventSource
web/src/graph/model.ts           GraphModel + pure reducers (merge, events, hide, save/load)
web/src/graph/style.ts           palettes, edgeWidth, stylesheet, toElements
web/src/graph/menu.ts            context-menu items per node kind
web/src/state/store.ts           zustand store (graph, selection, job, case, busy/error)
web/src/state/actions.ts         side-effecting actions (search, expand, trace, peel, cluster, tags, cases)
web/src/export/export.ts         edgesCsv, markdownReport, downloadText, exportPng
web/src/components/SearchBar.tsx
web/src/components/GraphCanvas.tsx
web/src/components/Inspector.tsx      (TxInspector, AddressInspector, FindingList, TagEditor)
web/src/components/TracePanel.tsx
web/src/components/CasePanel.tsx
web/src/components/KbBrowser.tsx
web/src/components/StatusBar.tsx
web/src/**/*.test.ts(x)          Vitest unit/component tests
web/e2e/fixtures.ts, web/e2e/workbench.spec.ts   Playwright smoke test with a mocked API
```

---

### Task 1: Scaffold the web app, theme tokens, formatting helpers

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`, `web/src/index.css`, `web/src/App.tsx` (placeholder), `web/src/test/setup.ts`, `web/src/lib/format.ts`
- Test: `web/src/lib/format.test.ts`, `web/src/App.test.tsx`

**Interfaces:**
- Produces:
  - `formatBtc(sats: number): string` (e.g. `"1.5 BTC"`, `"0 BTC"`)
  - `shortAddr(a: string): string`, `shortTxid(t: string): string`
  - `formatTime(ts: number | null | undefined): string` (UTC, or `"unconfirmed"`)
  - `btcToSats(btc: string): number | null`
  - `SATS_PER_BTC`

- [ ] **Step 1: Create the project files**

`web/package.json`:
```json
{
  "name": "btc-intel-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.62.0",
    "cytoscape": "^3.30.0",
    "cytoscape-dagre": "^2.5.0",
    "dompurify": "^3.2.0",
    "marked": "^15.0.0",
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.50.0",
    "@tailwindcss/vite": "^4.1.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.6.0",
    "@types/cytoscape-dagre": "^2.3.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "@vitejs/plugin-react": ">=4.6.0 <6",
    "jsdom": "^26.0.0",
    "tailwindcss": "^4.1.0",
    "typescript": "^5.8.0",
    "vite": "^7.0.0",
    "vitest": "^3.2.0"
  }
}
```

`web/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom", "node"]
  },
  "include": ["src", "e2e", "vite.config.ts", "playwright.config.ts"]
}
```

`web/vite.config.ts`:
```ts
/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8765" } },
  },
  preview: { host: "127.0.0.1", port: 4173 },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
```

`web/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>btc-intel workbench</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`web/src/index.css`:
```css
@import "tailwindcss";

:root {
  --bg: #f6f6f4;
  --panel: #ffffff;
  --panel-2: #f0f0ee;
  --text: #1b1b1f;
  --muted: #5f6368;
  --border: #dedede;
  --accent: #2f6fed;
  --danger: #c62828;
  --risk-none: #8a8f98;
  --risk-low: #2e9d5b;
  --risk-medium: #c98f00;
  --risk-high: #e0662e;
  --risk-severe: #d13a3a;
  --tx: #6b5bd6;
  --script: #9aa0a6;
  --taint: #e0662e;
  color-scheme: light;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111317;
    --panel: #181b21;
    --panel-2: #20242b;
    --text: #e8eaed;
    --muted: #9aa0a6;
    --border: #2d3139;
    --accent: #6ea0ff;
    --danger: #ff6b6b;
    --risk-none: #8a8f98;
    --risk-low: #4cc07e;
    --risk-medium: #e6b422;
    --risk-high: #ff8a4c;
    --risk-severe: #ff5c5c;
    --tx: #9a8cff;
    --script: #7d838c;
    --taint: #ff8a4c;
    color-scheme: dark;
  }
}

html, body, #root { height: 100%; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, sans-serif; }
.panel { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }
.muted { color: var(--muted); }
.btn { border: 1px solid var(--border); background: var(--panel-2); color: var(--text); border-radius: 6px; padding: 4px 10px; font-size: 13px; }
.btn:hover:not(:disabled) { border-color: var(--accent); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.input { border: 1px solid var(--border); background: var(--panel); color: var(--text); border-radius: 6px; padding: 4px 8px; font-size: 13px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.kb-article h1 { font-size: 1.5rem; font-weight: 700; margin: 0.5rem 0; }
.kb-article h2 { font-size: 1.15rem; font-weight: 600; margin: 1rem 0 0.25rem; }
.kb-article p, .kb-article li { line-height: 1.55; margin: 0.35rem 0; }
.kb-article ul { list-style: disc; padding-left: 1.25rem; }
.kb-article a { color: var(--accent); text-decoration: underline; }
.kb-article table { border-collapse: collapse; margin: 0.5rem 0; font-size: 0.9em; }
.kb-article th, .kb-article td { border: 1px solid var(--border); padding: 2px 6px; }
.kb-article code { font-family: ui-monospace, monospace; background: var(--panel-2); padding: 0 3px; border-radius: 3px; }
```

`web/src/test/setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

`web/src/main.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
```

`web/src/App.tsx` (placeholder, replaced in Task 9):
```tsx
export default function App() {
  return (
    <div className="h-full flex flex-col">
      <header className="px-4 py-2 border-b border-[var(--border)] font-semibold">btc-intel workbench</header>
    </div>
  );
}
```

- [ ] **Step 2: Install dependencies**

Run: `cd /home/fancybear/btc-intel/web && npm install`
Expected: installation completes and `package-lock.json` is created.

- [ ] **Step 3: Write the failing tests**

`web/src/lib/format.test.ts`:
```ts
import { btcToSats, formatBtc, formatTime, shortAddr, shortTxid } from "./format";

test("formatBtc trims trailing zeros and stays finite", () => {
  expect(formatBtc(0)).toBe("0 BTC");
  expect(formatBtc(150_000_000)).toBe("1.5 BTC");
  expect(formatBtc(100_000_000)).toBe("1 BTC");
  expect(formatBtc(10)).toBe("0.0000001 BTC");
  expect(formatBtc(2_100_000_000_000_000)).toBe("21000000 BTC");
});

test("short identifiers", () => {
  expect(shortAddr("bc1qntndgqfx46wks63jep34cjk3pw63es86kp45c6")).toBe("bc1qntnd…45c6");
  expect(shortAddr("1short")).toBe("1short");
  expect(shortTxid("c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c")).toBe("c5908e04…1c8c");
});

test("formatTime", () => {
  expect(formatTime(null)).toBe("unconfirmed");
  expect(formatTime(1749188499)).toBe("2025-06-06 05:41 UTC");
});

test("btcToSats", () => {
  expect(btcToSats("0.001")).toBe(100_000);
  expect(btcToSats("1.23456789")).toBe(123_456_789);
  expect(btcToSats("-1")).toBeNull();
  expect(btcToSats("abc")).toBeNull();
});
```

`web/src/App.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the workbench title", () => {
  render(<App />);
  expect(screen.getByText(/btc-intel workbench/i)).toBeInTheDocument();
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run`
Expected: FAIL (`./format` missing).

- [ ] **Step 4: Implement the helpers**

`web/src/lib/format.ts`:
```ts
export const SATS_PER_BTC = 100_000_000;

export function formatBtc(sats: number): string {
  const btc = (Number.isFinite(sats) ? sats : 0) / SATS_PER_BTC;
  return `${btc.toFixed(8).replace(/\.?0+$/, "")} BTC`;
}

export function shortAddr(a: string): string {
  return a.length <= 14 ? a : `${a.slice(0, 8)}…${a.slice(-4)}`;
}

export function shortTxid(t: string): string {
  return `${t.slice(0, 8)}…${t.slice(-4)}`;
}

export function formatTime(ts: number | null | undefined): string {
  if (!ts) return "unconfirmed";
  return `${new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16)} UTC`;
}

export function btcToSats(btc: string): number | null {
  const n = Number(btc);
  if (btc.trim() === "" || !Number.isFinite(n) || n < 0) return null;
  return Math.round(n * SATS_PER_BTC);
}
```

- [ ] **Step 5: Run the tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: 5 passed and no type errors.

```bash
cd /home/fancybear/btc-intel
git add web/package.json web/package-lock.json web/tsconfig.json web/vite.config.ts web/index.html web/src
git commit -m "feat(web): scaffold Vite/React workbench with theme tokens and formatting helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: API types, client and job event stream

**Files:**
- Create: `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/sse.ts`
- Test: `web/src/api/client.test.ts`, `web/src/api/sse.test.ts`

**Interfaces:**
- Produces:
  - Types: `RiskLevel`, `Tag`, `NewTag`, `AddressInfo`, `TxOut`, `TxIn`, `TxStatus`, `Tx`, `Finding`, `TxResponse`, `Outspend`, `AddressStats`, `ClusterMeta`, `AddressResponse`, `TxSummary`, `AddressTxsResponse`, `GraphNode`, `GraphEdge`, `StopReason`, `Stop`, `TracePolicy`, `TraceSeed`, `TraceResult`, `JobStatus`, `JobEvent`, `JobInfo<T>`, `PeelChain`, `ClusterResponse`, `CaseSummary`, `Case`, `SearchResponse`, `Heuristic`, `Technique`, `Incident`, `Category`
  - `class ApiError extends Error { status: number; incomplete: boolean }`
  - `api` object with these methods:
    - lookups: `health`, `search`, `tx`, `outspends`, `address`, `addressTxs`
    - jobs: `startTrace`, `peel`, `job`, `cancelJob`
    - clusters: `cluster`, `expandCluster`
    - tags: `tags`, `addTag`, `deleteTag`, `exportTags`
    - cases: `cases`, `createCase`, `getCase`, `updateCase`, `deleteCase`, `watch`, `unwatch`
    - knowledge base: `kb`, `kbPage`
  - `subscribeJob(jobId, onEvent, opts?) => () => void`. It closes after the final `status` event. On a transport error it emits a synthetic `{type:"status", status:"error"}`.

- [ ] **Step 1: Write the types**

`web/src/api/types.ts`:
```ts
export type RiskLevel = "none" | "low" | "medium" | "high" | "severe";

export interface Tag {
  id: number | null;
  address: string;
  label: string;
  category: string;
  abuse: string | null;
  actor: string | null;
  confidence: string;
  confidence_level: number;
  source: string;
  pack: string;
  is_cluster_definer: boolean;
  lastmod: string | null;
  created_by: string;
}

export interface NewTag {
  address: string;
  label: string;
  category: string;
  abuse?: string | null;
  actor?: string | null;
  source?: string;
  confidence?: string;
}

export interface AddressInfo {
  address: string;
  tags: Tag[];
  cluster: string | null;
  category: string | null;
  label: string | null;
  risk: RiskLevel;
  stop_category: string | null;
}

export interface TxOut { n: number; value: number; script_type: string; address: string | null; script_hex: string }
export interface TxStatus { confirmed: boolean; block_height: number | null; block_hash: string | null; block_time: number | null }
export interface TxIn {
  n: number;
  prev_txid: string;
  prev_vout: number;
  prevout: TxOut | null;
  is_coinbase: boolean;
  sequence: number;
  scriptsig_hex: string;
  scriptsig_asm: string;
  witness: string[];
  inner_redeemscript_asm: string | null;
  inner_witnessscript_asm: string | null;
}
export interface Tx {
  txid: string;
  version: number;
  locktime: number;
  vin: TxIn[];
  vout: TxOut[];
  size: number;
  weight: number;
  fee: number;
  status: TxStatus;
  is_coinbase: boolean;
  input_value: number;
  output_value: number;
  vsize: number;
  feerate: number;
}

export interface Finding {
  heuristic: string;
  subject: string;
  label: string;
  confidence: number;
  evidence: Record<string, unknown>;
}

export interface TxResponse {
  tx: Tx;
  findings: Finding[];
  flags: string[];
  addresses: Record<string, AddressInfo>;
  price_usd: number | null;
}

export interface Outspend { spent: boolean; txid: string | null; vin: number | null; status: TxStatus | null }

export interface AddressStats {
  address: string;
  tx_count: number;
  funded_txo_count: number;
  funded_sum: number;
  spent_txo_count: number;
  spent_sum: number;
  mempool_tx_count: number;
  mempool_delta: number;
  balance: number;
}

export interface ClusterMeta {
  root: string;
  size: number;
  partial: boolean;
  capped: boolean;
  expanded_at: number | null;
  calls_used: number;
}

export interface AddressResponse { stats: AddressStats; info: AddressInfo; cluster: ClusterMeta | null }

export interface TxSummary {
  txid: string;
  block_height: number | null;
  block_time: number | null;
  fee: number;
  n_in: number;
  n_out: number;
  value_out: number;
  delta: number | null;
  flags: string[];
}
export interface AddressTxsResponse { txs: TxSummary[]; next: string | null }

export type NodeKind = "tx" | "address" | "script";
export interface GraphNode { id: string; kind: NodeKind; label: string; data: Record<string, unknown> }
export interface GraphEdge { id: string; source: string; target: string; value: number; taint: number }
export type StopReason =
  | "unspent" | "labeled" | "coinjoin" | "max_hops" | "min_value" | "max_txs" | "coinbase" | "peel_off";
export interface Stop { node: string; reason: StopReason; taint: number; detail: string }

export interface TracePolicy {
  direction: "forward" | "backward";
  max_hops: number;
  max_txs: number;
  max_calls: number;
  min_value_sats: number;
  taint_model: "poison" | "haircut" | "fifo";
  stop_categories: string[] | null;
  coinjoin: "stop" | "through";
  peel_mode: boolean;
  max_address_txs: number;
}
export interface TraceSeed { txid?: string; vout?: number; address?: string }
export interface TraceResult {
  seed: TraceSeed;
  policy: TracePolicy;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stops: Stop[];
  incomplete: boolean;
  reason: string | null;
  calls_used: number;
  txs_expanded: number;
}

export type JobStatus = "running" | "done" | "error" | "cancelled";
export type JobEvent = { seq: number } & (
  | { type: "nodes"; items: GraphNode[] }
  | { type: "edges"; items: GraphEdge[] }
  | { type: "stop"; item: Stop }
  | { type: "done"; incomplete: boolean; reason: string | null; calls_used: number }
  | { type: "progress"; visited?: number; queued?: number; size?: number; calls?: number }
  | { type: "status"; status: JobStatus; error: string | null }
);
export interface JobInfo<T = unknown> {
  id: string;
  kind: string;
  status: JobStatus;
  error: string | null;
  events: number;
  result: T | null;
}

export interface PeelChain {
  start_txid: string;
  steps: { txid: string; remainder_vout: number; remainder_value: number;
    peels: { vout: number; address: string | null; value: number; label: string | null }[] }[];
  end_reason: "unspent" | "not_peel_shaped" | "max_steps" | "labeled" | "coinjoin" | "budget";
  end_txid: string | null;
  total_peeled: number;
}

export interface ClusterResponse {
  root: string | null;
  address?: string;
  meta?: ClusterMeta | null;
  members?: string[];
  tags?: Tag[];
  conflicts?: { labels: string[]; addresses: string[] }[];
  links?: { a: string; b: string; txid: string; heuristic: string }[];
}

export interface CaseSummary { id: string; name: string; created_at: number; updated_at: number; nodes: number }
export interface Case {
  id: string;
  name: string;
  notes: string;
  graph: Record<string, unknown>;
  created_at: number;
  updated_at: number;
  watch: string[];
}

export interface SearchResponse { kind: "txid" | "outpoint" | "address" | "text"; query: string; tags?: Tag[] }

export interface Heuristic {
  id: string; name: string; family: string; status: "implemented" | "planned" | "kb_only";
  implemented_by: string | null; parent: string | null; confidence: string; summary: string;
  signals: string[]; false_positives: string[]; refs: string[]; kb: string;
}
export interface Technique {
  id: string; name: string; tactic: string; summary: string; examples: string[]; evades: string[];
  detected_by: string[]; oak: string[]; fatf: string[]; refs: string[]; kb: string;
}
export interface Seed { kind: "address" | "tx"; value: string; role: string; ref: string; note: string | null }
export interface Incident {
  id: string; name: string; date: string; loss: string; btc: number | null; vector: string[];
  actor: string | null; attribution: string; techniques: string[]; summary: string; seeds: Seed[];
  seeds_note: string | null; refs: string[]; kb: string;
}
export interface Category {
  id: string; kind: "entity" | "abuse"; name: string; risk: RiskLevel; gs_concepts: string[];
  stop_trace: boolean; description: string;
}
```

- [ ] **Step 2: Write the failing client and SSE tests**

`web/src/api/client.test.ts`:
```ts
import { ApiError, api } from "./client";

function mockFetch(status: number, body: unknown, contentType = "application/json") {
  const fn = vi.fn().mockResolvedValue(
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "content-type": contentType },
    }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

test("builds URLs and parses JSON", async () => {
  const fetchFn = mockFetch(200, { kind: "text", query: "lazarus", tags: [] });
  const res = await api.search("lazarus group");
  expect(res.kind).toBe("text");
  expect(fetchFn.mock.calls[0][0]).toBe("/api/search?q=lazarus%20group");
});

test("posts JSON bodies", async () => {
  const fetchFn = mockFetch(202, { job_id: "j1" });
  await api.startTrace({ txid: "ab".repeat(32) }, { max_hops: 3 });
  const [url, init] = fetchFn.mock.calls[0];
  expect(url).toBe("/api/trace");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body)).toEqual({ seed: { txid: "ab".repeat(32) }, policy: { max_hops: 3 } });
});

test("maps error body to ApiError with incomplete", async () => {
  mockFetch(502, { detail: "all backends failed", incomplete: true });
  const err = await api.tx("ab".repeat(32)).catch((e) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err.status).toBe(502);
  expect(err.message).toBe("all backends failed");
  expect(err.incomplete).toBe(true);
});

test("handles 204 and text responses", async () => {
  mockFetch(204, "");
  expect(await api.deleteTag(3)).toBeUndefined();
  mockFetch(200, "title: t\ntags: []\n", "application/yaml");
  expect(await api.exportTags()).toContain("title: t");
});

test("non-JSON error bodies fall back to status text", async () => {
  mockFetch(500, "<html>oops</html>", "text/html");
  const err = await api.health().catch((e) => e);
  expect(err.status).toBe(500);
  expect(err.incomplete).toBe(false);
});
```

`web/src/api/sse.test.ts`:
```ts
import { subscribeJob } from "./sse";
import type { JobEvent } from "./types";

class FakeEventSource {
  static last: FakeEventSource;
  onmessage: ((m: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) { FakeEventSource.last = this; }
  close() { this.closed = true; }
  emit(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent); }
}

test("forwards events and closes after status", () => {
  const events: JobEvent[] = [];
  subscribeJob("j1", (e) => events.push(e), { EventSourceImpl: FakeEventSource as unknown as typeof EventSource });
  const es = FakeEventSource.last;
  expect(es.url).toBe("/api/jobs/j1/events");
  es.emit({ seq: 0, type: "stop", item: { node: "addr:x", reason: "unspent", taint: 1, detail: "" } });
  es.emit({ seq: 1, type: "status", status: "done", error: null });
  expect(events.map((e) => e.type)).toEqual(["stop", "status"]);
  expect(es.closed).toBe(true);
});

test("transport errors become a synthetic error status", () => {
  const events: JobEvent[] = [];
  subscribeJob("j2", (e) => events.push(e), { EventSourceImpl: FakeEventSource as unknown as typeof EventSource });
  FakeEventSource.last.onerror?.();
  expect(events).toEqual([{ seq: -1, type: "status", status: "error", error: "event stream disconnected" }]);
  expect(FakeEventSource.last.closed).toBe(true);
});

test("unsubscribe closes the stream", () => {
  const stop = subscribeJob("j3", () => {}, { EventSourceImpl: FakeEventSource as unknown as typeof EventSource });
  stop();
  expect(FakeEventSource.last.closed).toBe(true);
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/api`
Expected: FAIL.

- [ ] **Step 3: Implement the client and SSE helper**

`web/src/api/client.ts`:
```ts
import type {
  AddressResponse, AddressTxsResponse, Case, CaseSummary, ClusterResponse, JobInfo, NewTag, Outspend,
  PeelChain, SearchResponse, Tag, TracePolicy, TraceSeed, TxResponse,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string, public incomplete = false) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`;
    let incomplete = false;
    try {
      const body = await res.json();
      if (body && typeof body === "object") {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
        incomplete = Boolean(body.incomplete);
      }
    } catch {
      // non-JSON error body: keep the status text
    }
    throw new ApiError(res.status, detail, incomplete);
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const q = encodeURIComponent;

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),
  search: (query: string) => request<SearchResponse>(`/search?q=${q(query)}`),
  tx: (txid: string, price = false) => request<TxResponse>(`/tx/${txid}${price ? "?price=1" : ""}`),
  outspends: (txid: string) => request<Outspend[]>(`/tx/${txid}/outspends`),
  address: (address: string) => request<AddressResponse>(`/address/${address}`),
  addressTxs: (address: string, after?: string | null) =>
    request<AddressTxsResponse>(`/address/${address}/txs${after ? `?after=${after}` : ""}`),
  startTrace: (seed: TraceSeed, policy: Partial<TracePolicy>) =>
    request<{ job_id: string }>("/trace", post({ seed, policy })),
  peel: (txid: string, maxSteps = 50) => request<PeelChain>("/peel", post({ txid, max_steps: maxSteps })),
  job: <T>(id: string) => request<JobInfo<T>>(`/jobs/${id}`),
  cancelJob: (id: string) => request<{ cancelled: boolean }>(`/jobs/${id}`, { method: "DELETE" }),
  cluster: (address: string) => request<ClusterResponse>(`/cluster/${address}`),
  expandCluster: (address: string, policy?: Record<string, number>) =>
    request<{ job_id: string }>(`/cluster/${address}/expand`, post(policy ?? {})),
  tags: (address: string) => request<Tag[]>(`/tags?address=${q(address)}`),
  addTag: (tag: NewTag) => request<Tag>("/tags", post(tag)),
  deleteTag: (id: number) => request<void>(`/tags/${id}`, { method: "DELETE" }),
  exportTags: (pack = "user") => request<string>(`/tags/export?pack=${q(pack)}`),
  cases: () => request<CaseSummary[]>("/cases"),
  createCase: (body: { name: string; notes?: string; graph?: unknown }) => request<Case>("/cases", post(body)),
  getCase: (id: string) => request<Case>(`/cases/${id}`),
  updateCase: (id: string, patch: { name?: string; notes?: string; graph?: unknown }) =>
    request<Case>(`/cases/${id}`, { method: "PUT", body: JSON.stringify(patch) }),
  deleteCase: (id: string) => request<void>(`/cases/${id}`, { method: "DELETE" }),
  watch: (id: string, address: string) => request<Case>(`/cases/${id}/watch`, post({ address })),
  unwatch: (id: string, address: string) => request<Case>(`/cases/${id}/watch/${address}`, { method: "DELETE" }),
  kb: <T>(collection: "heuristics" | "techniques" | "incidents" | "categories" | "references") =>
    request<T[]>(`/kb/${collection}`),
  kbPage: (path: string) => request<{ path: string; markdown: string }>(`/kb-page?path=${q(path)}`),
};
```

`web/src/api/sse.ts`:
```ts
import type { JobEvent } from "./types";

export function subscribeJob(
  jobId: string,
  onEvent: (event: JobEvent) => void,
  opts: { EventSourceImpl?: typeof EventSource } = {},
): () => void {
  const Impl = opts.EventSourceImpl ?? EventSource;
  const source = new Impl(`/api/jobs/${jobId}/events`);
  let finished = false;
  source.onmessage = (message: MessageEvent) => {
    const event = JSON.parse(message.data) as JobEvent;
    onEvent(event);
    if (event.type === "status") {
      finished = true;
      source.close();
    }
  };
  source.onerror = () => {
    source.close();
    if (!finished) {
      finished = true;
      onEvent({ seq: -1, type: "status", status: "error", error: "event stream disconnected" });
    }
  };
  return () => {
    finished = true;
    source.close();
  };
}
```

- [ ] **Step 4: Run tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add web/src/api
git commit -m "feat(web): typed API client, error mapping and job event stream

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Graph model, styling and Cytoscape element mapping

**Files:**
- Create: `web/src/graph/model.ts`, `web/src/graph/style.ts`, `web/src/graph/menu.ts`
- Test: `web/src/test/fixtures.ts` (shared data), `web/src/graph/model.test.ts`, `web/src/graph/style.test.ts`, `web/src/graph/menu.test.ts`

**Interfaces:**
- Consumes: the Task 2 types and the Task 1 formatters.
- Produces:
  - `GraphModel { nodes: Record<string, GraphNode>; edges: Record<string, GraphEdge>; stops: Stop[]; hidden: string[]; positions: Record<string, {x:number;y:number}> }`
  - `SavedGraph { version: 1; nodes; edges; stops; hidden; positions }`
  - Pure reducers:
    - construction: `emptyGraph()`, `txNodeId(txid)`, `addrNodeId(address)`, `addressNode(address, info?)`
    - merging: `addNodes(m, nodes)`, `addEdges(m, edges)` (edge taint = max of old and new), `txToGraph(resp)`, `mergeTx(m, resp)`, `applyJobEvent(m, event)`, `mergeTrace(m, result)`
    - editing: `hideNodes(m, ids)`, `showAll(m)`, `removeNode(m, id)`, `setPositions(m, positions)`, `setClusterForAddresses(m, members: Set<string>, root)`, `addTagToNode(m, nodeId, tag, risk)`
    - queries: `stopsByNode(m)`, `stats(m)`
    - persistence: `toSaved(m)`, `fromSaved(value): GraphModel | null` (`null` for unknown shapes)
  - `Palette`, `LIGHT`, `DARK`, `currentPalette()`, `edgeWidth(value)` (in [1, 10]), `buildStylesheet(p)`, `toElements(m, p, { groupClusters })`
  - `MenuAction` union and `menuItems(kind): { action: MenuAction; label: string }[]`

- [ ] **Step 1: Write the shared fixture and the failing tests**

`web/src/test/fixtures.ts` (shared test data; not a test file, so importing it never re-registers tests):
```ts
import type { TxResponse } from "../api/types";

export const TXID = "aa".repeat(32);

export const txResponse: TxResponse = {
  tx: {
    txid: TXID, version: 2, locktime: 0, size: 200, weight: 800, fee: 1000, is_coinbase: false,
    input_value: 100_000, output_value: 99_000, vsize: 200, feerate: 5,
    status: { confirmed: true, block_height: 900000, block_hash: null, block_time: 1749188499 },
    vin: [{ n: 0, prev_txid: "bb".repeat(32), prev_vout: 0, is_coinbase: false, sequence: 0xfffffffd,
      prevout: { n: 0, value: 100_000, script_type: "v0_p2wpkh", address: "bc1qsrc", script_hex: "" },
      scriptsig_hex: "", scriptsig_asm: "", witness: [], inner_redeemscript_asm: null, inner_witnessscript_asm: null }],
    vout: [
      { n: 0, value: 60_000, script_type: "v0_p2wpkh", address: "bc1qdst", script_hex: "" },
      { n: 1, value: 39_000, script_type: "v0_p2wpkh", address: "bc1qchg", script_hex: "" },
      { n: 2, value: 0, script_type: "op_return", address: null, script_hex: "6a00" },
    ],
  },
  findings: [], flags: ["peel_step"], price_usd: null,
  addresses: { bc1qdst: { address: "bc1qdst", tags: [], cluster: null, category: "exchange", label: "Exchange", risk: "low", stop_category: "exchange" } },
};
```

`web/src/graph/model.test.ts`:
```ts
import { TXID, txResponse } from "../test/fixtures";
import {
  addEdges, addNodes, addTagToNode, applyJobEvent, emptyGraph, fromSaved, hideNodes, mergeTrace, mergeTx,
  removeNode, setClusterForAddresses, setPositions, stats, stopsByNode, toSaved,
} from "./model";


test("mergeTx builds a bipartite graph with script nodes", () => {
  const g = mergeTx(emptyGraph(), txResponse);
  expect(stats(g)).toEqual({ txs: 1, addresses: 3, scripts: 1, edges: 4, stops: 0 });
  expect(g.nodes[`tx:${TXID}`].data.flags).toEqual(["peel_step"]);
  expect(g.nodes["addr:bc1qdst"].label).toBe("Exchange");
  expect(g.edges[`in:${TXID}:0`]).toMatchObject({ source: "addr:bc1qsrc", target: `tx:${TXID}`, value: 100_000 });
  expect(g.edges[`out:${TXID}:2`].target).toBe(`script:${TXID}:2`);
});

test("merging keeps existing taint and positions", () => {
  let g = mergeTx(emptyGraph(), txResponse);
  g = addEdges(g, [{ ...g.edges[`out:${TXID}:0`], taint: 5000 }]);
  g = setPositions(g, { "addr:bc1qdst": { x: 10, y: 20 } });
  g = mergeTx(g, txResponse);
  expect(g.edges[`out:${TXID}:0`].taint).toBe(5000);
  expect(g.positions["addr:bc1qdst"]).toEqual({ x: 10, y: 20 });
});

test("applyJobEvent keeps hidden and positions", () => {
  let g = hideNodes(mergeTx(emptyGraph(), txResponse), ["addr:bc1qchg"]);
  g = setPositions(g, { [`tx:${TXID}`]: { x: 1, y: 2 } });
  g = applyJobEvent(g, { seq: 0, type: "nodes", items: [{ id: "addr:new", kind: "address", label: "new", data: {} }] });
  g = applyJobEvent(g, { seq: 1, type: "edges", items: [{ id: "out:x:0", source: `tx:${TXID}`, target: "addr:new", value: 5, taint: 5 }] });
  g = applyJobEvent(g, { seq: 2, type: "stop", item: { node: "addr:new", reason: "unspent", taint: 5, detail: "" } });
  expect(g.hidden).toEqual(["addr:bc1qchg"]);
  expect(g.positions[`tx:${TXID}`]).toEqual({ x: 1, y: 2 });
  expect(stopsByNode(g).get("addr:new")).toEqual(["unspent"]);
  expect(applyJobEvent(g, { seq: 3, type: "status", status: "done", error: null })).toBe(g);
});

test("mergeTrace merges nodes, edges and stops", () => {
  const g = mergeTrace(emptyGraph(), {
    seed: { txid: TXID }, policy: {} as never, incomplete: false, reason: null, calls_used: 3, txs_expanded: 1,
    nodes: [{ id: `tx:${TXID}`, kind: "tx", label: "aa", data: {} }],
    edges: [], stops: [{ node: `tx:${TXID}`, reason: "coinjoin", taint: 1, detail: "whirlpool" }],
  });
  expect(stats(g).stops).toBe(1);
});

test("removeNode drops incident edges; hide/show", () => {
  const g = removeNode(mergeTx(emptyGraph(), txResponse), `tx:${TXID}`);
  expect(stats(g).edges).toBe(0);
  expect(hideNodes(emptyGraph(), ["a", "a"]).hidden).toEqual(["a"]);
});

test("cluster and tag updates", () => {
  let g = mergeTx(emptyGraph(), txResponse);
  g = setClusterForAddresses(g, new Set(["bc1qsrc", "bc1qchg", "absent"]), "bc1qsrc");
  expect(g.nodes["addr:bc1qchg"].data.cluster).toBe("bc1qsrc");
  g = addTagToNode(g, "addr:bc1qchg", {
    id: 1, address: "bc1qchg", label: "Suspect", category: "perpetrator", abuse: "theft", actor: null,
    confidence: "forensic_investigation", confidence_level: 70, source: "analyst", pack: "user",
    is_cluster_definer: false, lastmod: null, created_by: "analyst",
  }, "severe");
  expect(g.nodes["addr:bc1qchg"].label).toBe("Suspect");
  expect(g.nodes["addr:bc1qchg"].data.risk).toBe("severe");
});

test("save/load roundtrip", () => {
  const g = setPositions(mergeTx(emptyGraph(), txResponse), { [`tx:${TXID}`]: { x: 3, y: 4 } });
  expect(fromSaved(JSON.parse(JSON.stringify(toSaved(g))))).toEqual(g);
});

test("fromSaved rejects unknown shapes", () => {
  expect(fromSaved({})).toBeNull();
  expect(fromSaved({ version: 2, nodes: [] })).toBeNull();
  expect(fromSaved(null)).toBeNull();
  expect(fromSaved({ version: 1, nodes: "x", edges: [], stops: [], hidden: [], positions: {} })).toBeNull();
});

test("addNodes merges data", () => {
  const g = addNodes(addNodes(emptyGraph(), [{ id: "n", kind: "address", label: "n", data: { a: 1 } }]),
    [{ id: "n", kind: "address", label: "n2", data: { b: 2 } }]);
  expect(g.nodes.n).toEqual({ id: "n", kind: "address", label: "n2", data: { a: 1, b: 2 } });
});
```

`web/src/graph/style.test.ts`:
```ts
import { emptyGraph, hideNodes, mergeTx, setClusterForAddresses } from "./model";
import { txResponse } from "../test/fixtures";
import { LIGHT, buildStylesheet, edgeWidth, toElements } from "./style";

test("edgeWidth is bounded", () => {
  expect(edgeWidth(0)).toBe(1);
  expect(edgeWidth(100_000)).toBe(1);
  expect(edgeWidth(100_000_000)).toBe(5.5);
  expect(edgeWidth(2_100_000_000_000_000)).toBe(10);
  expect(edgeWidth(Number.NaN)).toBe(1);
});

test("toElements colours addresses by risk and skips hidden", () => {
  const g = hideNodes(mergeTx(emptyGraph(), txResponse), ["addr:bc1qchg"]);
  const els = toElements(g, LIGHT, { groupClusters: false });
  const dst = els.find((e) => e.data.id === "addr:bc1qdst")!;
  expect(dst.data.color).toBe(LIGHT.risk.low);
  expect(els.some((e) => e.data.id === "addr:bc1qchg")).toBe(false);
  expect(els.some((e) => e.data.target === "addr:bc1qchg")).toBe(false);
  const edge = els.find((e) => e.data.id === `out:${"aa".repeat(32)}:0`)!;
  expect(edge.data.amount).toBe("0.0006 BTC");
});

test("clusters become compound parents when grouping", () => {
  const g = setClusterForAddresses(mergeTx(emptyGraph(), txResponse), new Set(["bc1qsrc", "bc1qchg"]), "bc1qsrc");
  const els = toElements(g, LIGHT, { groupClusters: true });
  expect(els[0].data.id).toBe("cluster:bc1qsrc");
  expect(els.find((e) => e.data.id === "addr:bc1qchg")!.data.parent).toBe("cluster:bc1qsrc");
  expect(toElements(g, LIGHT, { groupClusters: false }).some((e) => e.data.id === "cluster:bc1qsrc")).toBe(false);
});

test("stylesheet has selectors for every node kind", () => {
  const selectors = buildStylesheet(LIGHT).map((b) => b.selector);
  expect(selectors).toEqual(expect.arrayContaining(['node[kind = "address"]', 'node[kind = "tx"]', 'node[kind = "script"]', "edge"]));
});
```

`web/src/graph/menu.test.ts`:
```ts
import { menuItems } from "./menu";

test("menu items per kind", () => {
  expect(menuItems("tx").map((i) => i.action)).toEqual([
    "expand-outputs", "expand-inputs", "trace-forward", "trace-backward", "follow-peel", "hide", "remove",
  ]);
  expect(menuItems("address").map((i) => i.action)).toEqual([
    "trace-forward", "trace-backward", "expand-cluster", "select", "hide", "remove",
  ]);
  expect(menuItems("script").map((i) => i.action)).toEqual(["hide", "remove"]);
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/graph`
Expected: FAIL.

- [ ] **Step 2: Implement the model**

`web/src/graph/model.ts`:
```ts
import type {
  AddressInfo, GraphEdge, GraphNode, JobEvent, RiskLevel, Stop, Tag, TraceResult, TxResponse,
} from "../api/types";
import { shortAddr } from "../lib/format";

export interface Position { x: number; y: number }
export interface GraphModel {
  nodes: Record<string, GraphNode>;
  edges: Record<string, GraphEdge>;
  stops: Stop[];
  hidden: string[];
  positions: Record<string, Position>;
}
export interface SavedGraph {
  version: 1;
  nodes: GraphNode[];
  edges: GraphEdge[];
  stops: Stop[];
  hidden: string[];
  positions: Record<string, Position>;
}

export const emptyGraph = (): GraphModel => ({ nodes: {}, edges: {}, stops: [], hidden: [], positions: {} });
export const txNodeId = (txid: string) => `tx:${txid}`;
export const addrNodeId = (address: string) => `addr:${address}`;

const EMPTY_INFO = (address: string): AddressInfo => ({
  address, tags: [], cluster: null, category: null, label: null, risk: "none", stop_category: null,
});

export function addressNode(address: string, info?: AddressInfo): GraphNode {
  const data = info ?? EMPTY_INFO(address);
  return { id: addrNodeId(address), kind: "address", label: data.label ?? shortAddr(address), data: { ...data } };
}

export function addNodes(m: GraphModel, nodes: GraphNode[]): GraphModel {
  if (!nodes.length) return m;
  const next = { ...m.nodes };
  for (const n of nodes) {
    const old = next[n.id];
    next[n.id] = old ? { ...old, ...n, data: { ...old.data, ...n.data } } : n;
  }
  return { ...m, nodes: next };
}

export function addEdges(m: GraphModel, edges: GraphEdge[]): GraphModel {
  if (!edges.length) return m;
  const next = { ...m.edges };
  for (const e of edges) {
    const old = next[e.id];
    next[e.id] = { ...e, taint: Math.max(old?.taint ?? 0, e.taint) };
  }
  return { ...m, edges: next };
}

export function txToGraph(resp: TxResponse): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const { tx, addresses, flags } = resp;
  const txId = txNodeId(tx.txid);
  const nodes: GraphNode[] = [{
    id: txId, kind: "tx", label: tx.txid.slice(0, 8),
    data: {
      txid: tx.txid, block_height: tx.status.block_height, block_time: tx.status.block_time,
      confirmed: tx.status.confirmed, fee: tx.fee, n_in: tx.vin.length, n_out: tx.vout.length,
      value: tx.output_value, flags,
    },
  }];
  const edges: GraphEdge[] = [];
  for (const i of tx.vin) {
    const a = i.prevout?.address;
    if (!a) continue;
    nodes.push(addressNode(a, addresses[a]));
    edges.push({ id: `in:${tx.txid}:${i.n}`, source: addrNodeId(a), target: txId, value: i.prevout!.value, taint: 0 });
  }
  for (const o of tx.vout) {
    let target: string;
    if (o.address) {
      target = addrNodeId(o.address);
      nodes.push(addressNode(o.address, addresses[o.address]));
    } else {
      target = `script:${tx.txid}:${o.n}`;
      nodes.push({ id: target, kind: "script", label: o.script_type.toUpperCase(), data: { script_type: o.script_type, value: o.value } });
    }
    edges.push({ id: `out:${tx.txid}:${o.n}`, source: txId, target, value: o.value, taint: 0 });
  }
  return { nodes, edges };
}

export function mergeTx(m: GraphModel, resp: TxResponse): GraphModel {
  const { nodes, edges } = txToGraph(resp);
  return addEdges(addNodes(m, nodes), edges);
}

export function applyJobEvent(m: GraphModel, e: JobEvent): GraphModel {
  switch (e.type) {
    case "nodes":
      return addNodes(m, e.items);
    case "edges":
      return addEdges(m, e.items);
    case "stop":
      return { ...m, stops: [...m.stops, e.item] };
    default:
      return m;
  }
}

export function mergeTrace(m: GraphModel, r: TraceResult): GraphModel {
  const g = addEdges(addNodes(m, r.nodes), r.edges);
  return { ...g, stops: [...g.stops, ...r.stops] };
}

export function hideNodes(m: GraphModel, ids: string[]): GraphModel {
  return { ...m, hidden: [...new Set([...m.hidden, ...ids])] };
}

export function showAll(m: GraphModel): GraphModel {
  return { ...m, hidden: [] };
}

export function removeNode(m: GraphModel, id: string): GraphModel {
  const nodes = { ...m.nodes };
  delete nodes[id];
  const edges = Object.fromEntries(Object.entries(m.edges).filter(([, e]) => e.source !== id && e.target !== id));
  const positions = { ...m.positions };
  delete positions[id];
  return { ...m, nodes, edges, positions, hidden: m.hidden.filter((h) => h !== id), stops: m.stops.filter((s) => s.node !== id) };
}

export function setPositions(m: GraphModel, positions: Record<string, Position>): GraphModel {
  return { ...m, positions: { ...m.positions, ...positions } };
}

export function setClusterForAddresses(m: GraphModel, members: Set<string>, root: string): GraphModel {
  const updates: GraphNode[] = [];
  for (const address of members) {
    const node = m.nodes[addrNodeId(address)];
    if (node) updates.push({ ...node, data: { ...node.data, cluster: root } });
  }
  return addNodes(m, updates);
}

export function addTagToNode(m: GraphModel, nodeId: string, tag: Tag, risk: RiskLevel): GraphModel {
  const node = m.nodes[nodeId];
  if (!node) return m;
  const tags = [tag, ...((node.data.tags as Tag[] | undefined) ?? [])];
  const label = (node.data.label as string | null) ?? tag.label;
  return addNodes(m, [{ ...node, label, data: { ...node.data, tags, label, category: node.data.category ?? tag.category, risk } }]);
}

export function stopsByNode(m: GraphModel): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const s of m.stops) out.set(s.node, [...new Set([...(out.get(s.node) ?? []), s.reason])]);
  return out;
}

export function stats(m: GraphModel) {
  const nodes = Object.values(m.nodes);
  return {
    txs: nodes.filter((n) => n.kind === "tx").length,
    addresses: nodes.filter((n) => n.kind === "address").length,
    scripts: nodes.filter((n) => n.kind === "script").length,
    edges: Object.keys(m.edges).length,
    stops: m.stops.length,
  };
}

export function toSaved(m: GraphModel): SavedGraph {
  return { version: 1, nodes: Object.values(m.nodes), edges: Object.values(m.edges), stops: m.stops, hidden: m.hidden, positions: m.positions };
}

export function fromSaved(value: unknown): GraphModel | null {
  if (!value || typeof value !== "object") return null;
  const v = value as Partial<SavedGraph>;
  if (v.version !== 1 || !Array.isArray(v.nodes) || !Array.isArray(v.edges) || !Array.isArray(v.stops)
      || !Array.isArray(v.hidden) || typeof v.positions !== "object" || v.positions === null) {
    return null;
  }
  const g = addEdges(addNodes(emptyGraph(), v.nodes), v.edges);
  return { ...g, stops: v.stops, hidden: v.hidden, positions: v.positions };
}
```

- [ ] **Step 3: Implement styles, element mapping and the menu**

`web/src/graph/style.ts`:
```ts
import type { ElementDefinition } from "cytoscape";
import type { RiskLevel } from "../api/types";
import { formatBtc, shortAddr } from "../lib/format";
import { type GraphModel, stopsByNode } from "./model";

export interface Palette {
  text: string;
  muted: string;
  border: string;
  accent: string;
  tx: string;
  script: string;
  taint: string;
  risk: Record<RiskLevel, string>;
}

export const LIGHT: Palette = {
  text: "#1b1b1f", muted: "#5f6368", border: "#dedede", accent: "#2f6fed", tx: "#6b5bd6", script: "#9aa0a6",
  taint: "#e0662e",
  risk: { none: "#8a8f98", low: "#2e9d5b", medium: "#c98f00", high: "#e0662e", severe: "#d13a3a" },
};

export const DARK: Palette = {
  text: "#e8eaed", muted: "#9aa0a6", border: "#2d3139", accent: "#6ea0ff", tx: "#9a8cff", script: "#7d838c",
  taint: "#ff8a4c",
  risk: { none: "#8a8f98", low: "#4cc07e", medium: "#e6b422", high: "#ff8a4c", severe: "#ff5c5c" },
};

export function currentPalette(): Palette {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? DARK : LIGHT;
}

export function edgeWidth(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const w = 1 + 1.5 * Math.log10(Math.max(1, value / 100_000));
  return Math.min(10, Math.max(1, Number(w.toFixed(2))));
}

export interface StyleBlock { selector: string; style: Record<string, string | number> }

export function buildStylesheet(p: Palette): StyleBlock[] {
  return [
    { selector: "node", style: { label: "data(label)", "font-size": 10, color: p.text, "text-valign": "bottom", "text-margin-y": 4, "text-wrap": "ellipsis", "text-max-width": "140px" } },
    { selector: 'node[kind = "address"]', style: { shape: "ellipse", width: 26, height: 26, "background-color": "data(color)", "border-width": 1, "border-color": p.border } },
    { selector: 'node[kind = "tx"]', style: { shape: "round-rectangle", width: 18, height: 18, "background-color": p.tx } },
    { selector: 'node[kind = "script"]', style: { shape: "diamond", width: 14, height: 14, "background-color": p.script } },
    { selector: "node[?coinjoin]", style: { "border-width": 4, "border-color": p.risk.medium, "border-style": "double" } },
    { selector: "node[stop]", style: { "border-width": 3, "border-color": p.accent } },
    { selector: ":parent", style: { "background-opacity": 0.06, "border-color": p.muted, "border-style": "dashed", "text-valign": "top", "text-halign": "center" } },
    { selector: "edge", style: { width: "data(width)", "line-color": p.muted, "target-arrow-color": p.muted, "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.8, label: "data(amount)", "font-size": 8, color: p.muted, "text-rotation": "autorotate" } },
    { selector: "edge[taint > 0]", style: { "line-color": p.taint, "target-arrow-color": p.taint } },
    { selector: ":selected", style: { "overlay-color": p.accent, "overlay-opacity": 0.25, "overlay-padding": 6 } },
  ];
}

export function toElements(m: GraphModel, p: Palette, opts: { groupClusters: boolean }): ElementDefinition[] {
  const hidden = new Set(m.hidden);
  const stops = stopsByNode(m);
  const visible = Object.values(m.nodes).filter((n) => !hidden.has(n.id));
  const clusterSize = new Map<string, number>();
  if (opts.groupClusters) {
    for (const n of visible) {
      const c = n.kind === "address" ? (n.data.cluster as string | null) : null;
      if (c) clusterSize.set(c, (clusterSize.get(c) ?? 0) + 1);
    }
  }
  const els: ElementDefinition[] = [];
  for (const [root, count] of clusterSize) {
    if (count >= 2) els.push({ group: "nodes", data: { id: `cluster:${root}`, label: `cluster ${shortAddr(root)} (${count})`, kind: "cluster" } });
  }
  for (const n of visible) {
    const cluster = n.kind === "address" ? (n.data.cluster as string | null) : null;
    const flags = (n.data.flags as string[] | undefined) ?? [];
    const risk = (n.data.risk as RiskLevel | undefined) ?? "none";
    els.push({
      group: "nodes",
      data: {
        id: n.id, label: n.label, kind: n.kind, risk,
        color: n.kind === "address" ? p.risk[risk] ?? p.risk.none : undefined,
        coinjoin: flags.some((f) => f.startsWith("coinjoin:")) || undefined,
        stop: stops.get(n.id)?.join(","),
        parent: cluster && (clusterSize.get(cluster) ?? 0) >= 2 ? `cluster:${cluster}` : undefined,
      },
      position: m.positions[n.id] ? { ...m.positions[n.id] } : undefined,
    });
  }
  for (const e of Object.values(m.edges)) {
    if (hidden.has(e.source) || hidden.has(e.target) || !m.nodes[e.source] || !m.nodes[e.target]) continue;
    els.push({ group: "edges", data: { id: e.id, source: e.source, target: e.target, value: e.value, taint: e.taint, width: edgeWidth(e.value), amount: formatBtc(e.value) } });
  }
  return els;
}
```

`web/src/graph/menu.ts`:
```ts
import type { NodeKind } from "../api/types";

export type MenuAction =
  | "expand-outputs" | "expand-inputs" | "trace-forward" | "trace-backward" | "follow-peel"
  | "expand-cluster" | "select" | "hide" | "remove";

const ITEMS: Record<NodeKind, { action: MenuAction; label: string }[]> = {
  tx: [
    { action: "expand-outputs", label: "Expand outputs (who received)" },
    { action: "expand-inputs", label: "Expand inputs (where from)" },
    { action: "trace-forward", label: "Trace forward from here" },
    { action: "trace-backward", label: "Trace backward from here" },
    { action: "follow-peel", label: "Follow peel chain" },
    { action: "hide", label: "Hide" },
    { action: "remove", label: "Remove from graph" },
  ],
  address: [
    { action: "trace-forward", label: "Trace forward (received funds)" },
    { action: "trace-backward", label: "Trace backward (source of funds)" },
    { action: "expand-cluster", label: "Expand cluster (common-input)" },
    { action: "select", label: "Inspect / tag" },
    { action: "hide", label: "Hide" },
    { action: "remove", label: "Remove from graph" },
  ],
  script: [
    { action: "hide", label: "Hide" },
    { action: "remove", label: "Remove from graph" },
  ],
};

export function menuItems(kind: NodeKind) {
  return ITEMS[kind];
}
```

- [ ] **Step 4: Run tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add web/src/graph web/src/test/fixtures.ts
git commit -m "feat(web): pure graph model, risk-coloured Cytoscape mapping and context-menu definitions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Workbench store and actions

**Files:**
- Create: `web/src/state/store.ts`, `web/src/state/actions.ts`
- Test: `web/src/state/actions.test.ts`

**Interfaces:**
- Consumes: `api`, `ApiError`, `subscribeJob`, the graph reducers.
- Produces:
  - `useWorkbench` (zustand) with state `graph, selected, groupClusters, caseId, caseName, notes, dirty, job, busy, error, message` and setters `updateGraph(fn), select(id), setError(msg), setMessage(msg), setJob(job), patchJob(patch), begin(), end(), setGroupClusters(v), setCase({id,name,notes,graph?}), setCaseName(name), setNotes(n), markClean(), reset()`
  - `JobState { id; kind: "trace"|"cluster"; status; nodes; stops; error; reason; calls }`
  - Actions:
    - navigation: `search(q) -> Promise<SearchResponse | undefined>`, `openTx(txid)`, `openAddress(address)`
    - expansion: `expandOutputs(txid)`, `expandInputs(txid)`, `followPeel(txid)`
    - jobs: `startTrace(seed, policy)`, `cancelJob()`, `expandCluster(address)`, `applyClusterToGraph(address)`
    - tags: `addTag(tag)`
    - cases: `saveCase()`, `loadCase(id)`, `newCase()`, `deleteCase(id)`, `watchAddress(address)`
    - `EXPAND_LIMIT = 25`

- [ ] **Step 1: Write the failing tests**

`web/src/state/actions.test.ts`:
```ts
import { txResponse } from "../test/fixtures";
import type { JobEvent } from "../api/types";

const handlers: { onEvent?: (e: JobEvent) => void } = {};

vi.mock("../api/sse", () => ({
  subscribeJob: (_id: string, onEvent: (e: JobEvent) => void) => {
    handlers.onEvent = onEvent;
    return () => {};
  },
}));

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      search: vi.fn(), tx: vi.fn(), outspends: vi.fn(), address: vi.fn(), startTrace: vi.fn(), peel: vi.fn(),
      cancelJob: vi.fn(), expandCluster: vi.fn(), cluster: vi.fn(), addTag: vi.fn(), kb: vi.fn(),
      createCase: vi.fn(), updateCase: vi.fn(), getCase: vi.fn(), deleteCase: vi.fn(), watch: vi.fn(),
    },
  };
});

import { ApiError, api } from "../api/client";
import * as actions from "./actions";
import { useWorkbench } from "./store";

const TXID = "aa".repeat(32);
const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

beforeEach(() => {
  useWorkbench.getState().reset();
  Object.values(mocked).forEach((fn) => fn.mockReset());
});

test("search for a txid opens it and selects the tx node", async () => {
  mocked.search.mockResolvedValue({ kind: "txid", query: TXID });
  mocked.tx.mockResolvedValue(txResponse);
  await actions.search(TXID);
  const s = useWorkbench.getState();
  expect(s.selected).toBe(`tx:${TXID}`);
  expect(Object.keys(s.graph.nodes)).toContain("addr:bc1qdst");
  expect(s.busy).toBe(0);
});

test("text search with no tags sets a message", async () => {
  mocked.search.mockResolvedValue({ kind: "text", query: "zzz", tags: [] });
  const res = await actions.search("zzz");
  expect(res?.kind).toBe("text");
  expect(useWorkbench.getState().message).toMatch(/No transaction, address or tag/);
});

test("API errors surface as messages, incomplete marked partial", async () => {
  mocked.tx.mockRejectedValue(new ApiError(502, "all backends failed", true));
  await actions.openTx(TXID);
  expect(useWorkbench.getState().error).toMatch(/all backends failed.*partial/);
});

test("expandOutputs fetches each distinct spending tx, capped", async () => {
  const spends = Array.from({ length: 30 }, (_, i) => ({ spent: true, txid: `${i}`.padStart(64, "0"), vin: 0, status: null }));
  mocked.outspends.mockResolvedValue([...spends, spends[0], { spent: false, txid: null, vin: null, status: null }]);
  mocked.tx.mockResolvedValue(txResponse);
  const n = await actions.expandOutputs(TXID);
  expect(n).toBe(actions.EXPAND_LIMIT);
  expect(mocked.tx).toHaveBeenCalledTimes(actions.EXPAND_LIMIT);
});

test("startTrace applies streamed events and records incomplete reason", async () => {
  mocked.startTrace.mockResolvedValue({ job_id: "j1" });
  await actions.startTrace({ txid: TXID }, { max_hops: 2 });
  expect(useWorkbench.getState().job?.status).toBe("running");
  handlers.onEvent!({ seq: 0, type: "nodes", items: [{ id: `tx:${TXID}`, kind: "tx", label: "aa", data: {} }] });
  handlers.onEvent!({ seq: 1, type: "stop", item: { node: `tx:${TXID}`, reason: "coinjoin", taint: 1, detail: "" } });
  handlers.onEvent!({ seq: 2, type: "done", incomplete: true, reason: "API call budget of 2 exhausted", calls_used: 2 });
  handlers.onEvent!({ seq: 3, type: "status", status: "done", error: null });
  const s = useWorkbench.getState();
  expect(s.job).toMatchObject({ status: "done", nodes: 1, stops: 1, reason: "API call budget of 2 exhausted", calls: 2 });
  expect(s.message).toMatch(/partial/i);
});

test("expandCluster applies membership on completion", async () => {
  mocked.tx.mockResolvedValue(txResponse);
  await actions.openTx(TXID);
  mocked.expandCluster.mockResolvedValue({ job_id: "c1" });
  mocked.cluster.mockResolvedValue({ root: "bc1qsrc", members: ["bc1qsrc", "bc1qchg"] });
  await actions.expandCluster("bc1qsrc");
  handlers.onEvent!({ seq: 0, type: "progress", size: 2, calls: 5 });
  handlers.onEvent!({ seq: 1, type: "status", status: "done", error: null });
  await vi.waitFor(() => expect(useWorkbench.getState().graph.nodes["addr:bc1qchg"].data.cluster).toBe("bc1qsrc"));
});

test("addTag updates the node with risk from categories", async () => {
  mocked.tx.mockResolvedValue(txResponse);
  await actions.openTx(TXID);
  mocked.kb.mockResolvedValue([
    { id: "perpetrator", risk: "high" }, { id: "theft", risk: "severe" },
  ]);
  mocked.addTag.mockResolvedValue({
    id: 1, address: "bc1qchg", label: "Suspect", category: "perpetrator", abuse: "theft", actor: null,
    confidence: "forensic_investigation", confidence_level: 70, source: "analyst", pack: "user",
    is_cluster_definer: false, lastmod: null, created_by: "analyst",
  });
  await actions.addTag({ address: "bc1qchg", label: "Suspect", category: "perpetrator", abuse: "theft" });
  expect(useWorkbench.getState().graph.nodes["addr:bc1qchg"].data.risk).toBe("severe");
});

test("save creates then updates a case; load restores the graph", async () => {
  mocked.tx.mockResolvedValue(txResponse);
  await actions.openTx(TXID);
  useWorkbench.getState().setCaseName("Case A");
  mocked.createCase.mockResolvedValue({ id: "k1", name: "Case A", notes: "", graph: {}, created_at: 1, updated_at: 1, watch: [] });
  await actions.saveCase();
  expect(mocked.createCase.mock.calls[0][0].graph.version).toBe(1);
  expect(useWorkbench.getState()).toMatchObject({ caseId: "k1", dirty: false });
  mocked.updateCase.mockResolvedValue({ id: "k1" });
  await actions.saveCase();
  expect(mocked.updateCase).toHaveBeenCalledWith("k1", expect.objectContaining({ name: "Case A" }));
  const saved = mocked.createCase.mock.calls[0][0].graph;
  actions.newCase();
  mocked.getCase.mockResolvedValue({ id: "k1", name: "Case A", notes: "n", graph: saved, created_at: 1, updated_at: 2, watch: [] });
  await actions.loadCase("k1");
  expect(Object.keys(useWorkbench.getState().graph.nodes)).toContain(`tx:${TXID}`);
  mocked.getCase.mockResolvedValue({ id: "k2", name: "Old", notes: "", graph: { weird: true }, created_at: 1, updated_at: 2, watch: [] });
  await actions.loadCase("k2");
  expect(useWorkbench.getState().message).toMatch(/could not be read/);
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/state`
Expected: FAIL.

- [ ] **Step 2: Implement the store**

`web/src/state/store.ts`:
```ts
import { create } from "zustand";
import type { JobStatus } from "../api/types";
import { type GraphModel, emptyGraph } from "../graph/model";

export interface JobState {
  id: string;
  kind: "trace" | "cluster";
  status: JobStatus;
  nodes: number;
  stops: number;
  error: string | null;
  reason: string | null;
  calls: number | null;
}

interface Data {
  graph: GraphModel;
  selected: string | null;
  groupClusters: boolean;
  caseId: string | null;
  caseName: string;
  notes: string;
  dirty: boolean;
  job: JobState | null;
  busy: number;
  error: string | null;
  message: string | null;
}

export interface WorkbenchState extends Data {
  updateGraph: (fn: (g: GraphModel) => GraphModel) => void;
  select: (id: string | null) => void;
  setError: (msg: string | null) => void;
  setMessage: (msg: string | null) => void;
  setJob: (job: JobState | null) => void;
  patchJob: (patch: Partial<JobState>) => void;
  begin: () => void;
  end: () => void;
  setGroupClusters: (value: boolean) => void;
  setCase: (c: { id: string | null; name: string; notes: string; graph?: GraphModel }) => void;
  setCaseName: (name: string) => void;
  setNotes: (notes: string) => void;
  markClean: () => void;
  reset: () => void;
}

const initial = (): Data => ({
  graph: emptyGraph(), selected: null, groupClusters: true, caseId: null, caseName: "", notes: "",
  dirty: false, job: null, busy: 0, error: null, message: null,
});

export const useWorkbench = create<WorkbenchState>()((set) => ({
  ...initial(),
  updateGraph: (fn) => set((s) => ({ graph: fn(s.graph), dirty: true })),
  select: (id) => set({ selected: id }),
  setError: (error) => set({ error }),
  setMessage: (message) => set({ message }),
  setJob: (job) => set({ job }),
  patchJob: (patch) => set((s) => (s.job ? { job: { ...s.job, ...patch } } : {})),
  begin: () => set((s) => ({ busy: s.busy + 1 })),
  end: () => set((s) => ({ busy: Math.max(0, s.busy - 1) })),
  setGroupClusters: (groupClusters) => set({ groupClusters }),
  setCase: ({ id, name, notes, graph }) =>
    set((s) => ({ caseId: id, caseName: name, notes, graph: graph ?? s.graph, selected: null })),
  setCaseName: (caseName) => set({ caseName, dirty: true }),
  setNotes: (notes) => set({ notes, dirty: true }),
  markClean: () => set({ dirty: false }),
  reset: () => set(initial()),
}));
```

- [ ] **Step 3: Implement the actions**

`web/src/state/actions.ts`:
```ts
import { ApiError, api } from "../api/client";
import { subscribeJob } from "../api/sse";
import type { Category, NewTag, RiskLevel, SearchResponse, TracePolicy, TraceSeed } from "../api/types";
import {
  addNodes, addTagToNode, addrNodeId, addressNode, applyJobEvent, emptyGraph, fromSaved, mergeTx,
  setClusterForAddresses, toSaved, txNodeId,
} from "../graph/model";
import { useWorkbench } from "./store";

export const EXPAND_LIMIT = 25;
const RISK_ORDER: RiskLevel[] = ["none", "low", "medium", "high", "severe"];
const st = () => useWorkbench.getState();
let unsubscribe: (() => void) | null = null;
let categories: Promise<Category[]> | null = null;

function describe(e: unknown): string {
  if (e instanceof ApiError) {
    return e.incomplete ? `${e.message} — partial result (public API limits); retry or narrow the query` : e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

async function guarded<T>(fn: () => Promise<T>): Promise<T | undefined> {
  st().begin();
  st().setError(null);
  try {
    return await fn();
  } catch (e) {
    st().setError(describe(e));
    return undefined;
  } finally {
    st().end();
  }
}

export async function search(q: string): Promise<SearchResponse | undefined> {
  st().setMessage(null);
  const res = await guarded(() => api.search(q.trim()));
  if (!res) return undefined;
  if (res.kind === "txid") await openTx(res.query);
  else if (res.kind === "outpoint") await openTx(res.query.split(":")[0]);
  else if (res.kind === "address") await openAddress(res.query);
  else if (!res.tags?.length) st().setMessage(`No transaction, address or tag matches "${q}"`);
  return res;
}

export const openTx = (txid: string) =>
  guarded(async () => {
    const resp = await api.tx(txid);
    st().updateGraph((g) => mergeTx(g, resp));
    st().select(txNodeId(txid));
    return resp;
  });

export const openAddress = (address: string) =>
  guarded(async () => {
    const resp = await api.address(address);
    st().updateGraph((g) => addNodes(g, [addressNode(address, resp.info)]));
    st().select(addrNodeId(address));
    return resp;
  });

export const expandOutputs = (txid: string) =>
  guarded(async () => {
    const spends = await api.outspends(txid);
    const children = [...new Set(spends.filter((s) => s.spent && s.txid).map((s) => s.txid as string))].slice(0, EXPAND_LIMIT);
    for (const child of children) {
      const resp = await api.tx(child);
      st().updateGraph((g) => mergeTx(g, resp));
    }
    return children.length;
  });

export const expandInputs = (txid: string) =>
  guarded(async () => {
    const resp = await api.tx(txid);
    st().updateGraph((g) => mergeTx(g, resp));
    const parents = [...new Set(resp.tx.vin.filter((i) => !i.is_coinbase).map((i) => i.prev_txid))].slice(0, EXPAND_LIMIT);
    for (const parent of parents) {
      const p = await api.tx(parent);
      st().updateGraph((g) => mergeTx(g, p));
    }
    return parents.length;
  });

export const followPeel = (txid: string) =>
  guarded(async () => {
    const chain = await api.peel(txid);
    for (const step of chain.steps.slice(0, EXPAND_LIMIT)) {
      const resp = await api.tx(step.txid);
      st().updateGraph((g) => mergeTx(g, resp));
    }
    st().setMessage(`Peel chain: ${chain.steps.length} steps, ended: ${chain.end_reason}`);
    return chain;
  });

function listen(jobId: string, kind: "trace" | "cluster", onDone?: () => Promise<void>) {
  unsubscribe?.();
  st().setJob({ id: jobId, kind, status: "running", nodes: 0, stops: 0, error: null, reason: null, calls: null });
  unsubscribe = subscribeJob(jobId, (e) => {
    if (e.type === "nodes" || e.type === "edges" || e.type === "stop") {
      st().updateGraph((g) => applyJobEvent(g, e));
      const g = st().graph;
      st().patchJob({ nodes: Object.keys(g.nodes).length, stops: g.stops.length });
    } else if (e.type === "progress") {
      st().patchJob({ calls: e.calls ?? null, nodes: e.size ?? 0 });
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

export async function startTrace(seed: TraceSeed, policy: Partial<TracePolicy>) {
  st().setMessage(null);
  const res = await guarded(() => api.startTrace(seed, policy));
  if (res) listen(res.job_id, "trace");
}

export async function cancelJob() {
  const job = st().job;
  if (job && job.status === "running") await guarded(() => api.cancelJob(job.id));
}

export async function applyClusterToGraph(address: string) {
  const c = await guarded(() => api.cluster(address));
  if (c?.root && c.members) {
    const root = c.root;
    const members = new Set(c.members);
    st().updateGraph((g) => setClusterForAddresses(g, members, root));
  }
}

export async function expandCluster(address: string, policy?: Record<string, number>) {
  const res = await guarded(() => api.expandCluster(address, policy));
  if (res) listen(res.job_id, "cluster", () => applyClusterToGraph(address));
}

async function riskOf(category: string, abuse: string | null | undefined): Promise<RiskLevel> {
  categories ??= api.kb<Category>("categories").catch(() => []);
  const byId = new Map((await categories).map((c) => [c.id, c.risk]));
  const levels = [byId.get(category) ?? "none", abuse ? byId.get(abuse) ?? "none" : "none"];
  return levels.reduce((a, b) => (RISK_ORDER.indexOf(b) > RISK_ORDER.indexOf(a) ? b : a), "none");
}

export const addTag = (tag: NewTag) =>
  guarded(async () => {
    const stored = await api.addTag(tag);
    const risk = await riskOf(stored.category, stored.abuse);
    st().updateGraph((g) => addTagToNode(g, addrNodeId(stored.address), stored, risk));
    return stored;
  });

export const saveCase = () =>
  guarded(async () => {
    const s = st();
    const graph = toSaved(s.graph);
    const name = s.caseName.trim() || "Untitled case";
    if (s.caseId) {
      await api.updateCase(s.caseId, { name, notes: s.notes, graph });
    } else {
      const created = await api.createCase({ name, notes: s.notes, graph });
      st().setCase({ id: created.id, name: created.name, notes: s.notes });
    }
    st().markClean();
  });

export const loadCase = (id: string) =>
  guarded(async () => {
    const c = await api.getCase(id);
    const graph = fromSaved(c.graph);
    st().setCase({ id: c.id, name: c.name, notes: c.notes, graph: graph ?? emptyGraph() });
    st().markClean();
    st().setMessage(graph ? null : `Case "${c.name}" graph could not be read (unknown format); starting empty`);
    return c;
  });

export function newCase() {
  unsubscribe?.();
  unsubscribe = null;
  st().reset();
}

export const deleteCase = (id: string) =>
  guarded(async () => {
    await api.deleteCase(id);
    if (st().caseId === id) newCase();
  });

export const watchAddress = (address: string) =>
  guarded(async () => {
    const id = st().caseId;
    if (!id) throw new Error("Save the case before adding watch addresses");
    return api.watch(id, address);
  });
```

- [ ] **Step 4: Run tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add web/src/state
git commit -m "feat(web): workbench store and actions (search, expand, trace streaming, clusters, tags, cases)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Graph canvas (Cytoscape + dagre + context menu)

**Files:**
- Create: `web/src/components/GraphCanvas.tsx`, `web/src/components/StatusBar.tsx`
- Test: `web/src/components/StatusBar.test.tsx`

**Interfaces:**
- Consumes: `useWorkbench`, `toElements`, `buildStylesheet`, `currentPalette`, `menuItems`, and the actions `expandOutputs`, `expandInputs`, `followPeel`, `startTrace`, `expandCluster`.
- Produces:
  - `<GraphCanvas onExport={(cy) => void} />`, which renders the model and syncs elements incrementally. It re-runs the dagre layout (left to right) when nodes are added, saves positions on drag, selects on tap, and shows a context menu on right-click.
  - `<StatusBar />`, which shows `data-testid="graph-stats"` with the text `"N txs · M addresses · K edges · S stops"`, plus the busy, error and job status.

The canvas is exercised by the Playwright test in Task 10; jsdom cannot render Cytoscape. The pure pieces it depends on are unit-tested in Task 3.

- [ ] **Step 1: Write the failing StatusBar test**

`web/src/components/StatusBar.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { txResponse } from "../test/fixtures";
import { mergeTx } from "../graph/model";
import { useWorkbench } from "../state/store";
import StatusBar from "./StatusBar";

beforeEach(() => useWorkbench.getState().reset());

test("shows graph counts, errors and job state", () => {
  useWorkbench.getState().updateGraph((g) => mergeTx(g, txResponse));
  useWorkbench.getState().setError("all backends failed");
  useWorkbench.getState().setJob({ id: "j", kind: "trace", status: "running", nodes: 4, stops: 1, error: null, reason: null, calls: 12 });
  render(<StatusBar />);
  expect(screen.getByTestId("graph-stats")).toHaveTextContent("1 txs · 3 addresses · 4 edges · 0 stops");
  expect(screen.getByRole("alert")).toHaveTextContent("all backends failed");
  expect(screen.getByText(/trace running/i)).toBeInTheDocument();
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/components/StatusBar.test.tsx`
Expected: FAIL.

- [ ] **Step 2: Implement StatusBar and GraphCanvas**

`web/src/components/StatusBar.tsx`:
```tsx
import { stats } from "../graph/model";
import { useWorkbench } from "../state/store";

export default function StatusBar() {
  const graph = useWorkbench((s) => s.graph);
  const busy = useWorkbench((s) => s.busy);
  const error = useWorkbench((s) => s.error);
  const message = useWorkbench((s) => s.message);
  const job = useWorkbench((s) => s.job);
  const n = stats(graph);
  return (
    <footer className="flex items-center gap-4 px-3 py-1 text-xs border-t border-[var(--border)] bg-[var(--panel)]">
      <span data-testid="graph-stats">{`${n.txs} txs · ${n.addresses} addresses · ${n.edges} edges · ${n.stops} stops`}</span>
      {busy > 0 && <span className="muted">loading… (public APIs are rate-limited)</span>}
      {job && (
        <span className="muted">
          {job.kind} {job.status}
          {job.calls !== null ? ` · ${job.calls} API calls` : ""}
          {job.reason ? ` · ${job.reason}` : ""}
        </span>
      )}
      {message && <span>{message}</span>}
      {error && <span role="alert" className="text-[var(--danger)]">{error}</span>}
    </footer>
  );
}
```

`web/src/components/GraphCanvas.tsx`:
```tsx
import cytoscape, { type Core, type StylesheetStyle } from "cytoscape";
import dagre from "cytoscape-dagre";
import { useEffect, useMemo, useRef, useState } from "react";
import type { NodeKind } from "../api/types";
import { type MenuAction, menuItems } from "../graph/menu";
import { hideNodes, removeNode, setPositions } from "../graph/model";
import { buildStylesheet, currentPalette, toElements } from "../graph/style";
import { expandCluster, expandInputs, expandOutputs, followPeel, startTrace } from "../state/actions";
import { useWorkbench } from "../state/store";

cytoscape.use(dagre);

interface Menu { x: number; y: number; id: string; kind: NodeKind }

export async function runMenuAction(action: MenuAction, id: string) {
  const store = useWorkbench.getState();
  const [prefix, ...rest] = id.split(":");
  const value = rest.join(":");
  switch (action) {
    case "expand-outputs": return expandOutputs(value);
    case "expand-inputs": return expandInputs(value);
    case "follow-peel": return followPeel(value);
    case "trace-forward":
    case "trace-backward": {
      const direction = action === "trace-forward" ? "forward" : "backward";
      const seed = prefix === "tx" ? { txid: value } : { address: value };
      return startTrace(seed, { direction });
    }
    case "expand-cluster": return expandCluster(value);
    case "select": return store.select(id);
    case "hide": return store.updateGraph((g) => hideNodes(g, [id]));
    case "remove": return store.updateGraph((g) => removeNode(g, id));
  }
}

export default function GraphCanvas({ onReady }: { onReady?: (cy: Core) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [menu, setMenu] = useState<Menu | null>(null);
  const graph = useWorkbench((s) => s.graph);
  const groupClusters = useWorkbench((s) => s.groupClusters);
  const selected = useWorkbench((s) => s.selected);
  const palette = useMemo(() => currentPalette(), []);
  const elements = useMemo(() => toElements(graph, palette, { groupClusters }), [graph, palette, groupClusters]);

  useEffect(() => {
    const cy = cytoscape({
      container: container.current,
      style: buildStylesheet(palette) as unknown as StylesheetStyle[],
      wheelSensitivity: 0.3,
      minZoom: 0.05,
      maxZoom: 4,
    });
    cy.on("tap", "node", (e) => {
      setMenu(null);
      const kind = e.target.data("kind");
      if (kind !== "cluster") useWorkbench.getState().select(e.target.id());
    });
    cy.on("tap", (e) => {
      if (e.target === cy) {
        setMenu(null);
        useWorkbench.getState().select(null);
      }
    });
    cy.on("cxttap", "node", (e) => {
      const kind = e.target.data("kind");
      if (kind === "cluster") return;
      setMenu({ x: e.renderedPosition.x, y: e.renderedPosition.y, id: e.target.id(), kind });
    });
    cy.on("dragfree", "node", (e) => {
      const pos = e.target.position();
      useWorkbench.getState().updateGraph((g) => setPositions(g, { [e.target.id()]: { x: pos.x, y: pos.y } }));
    });
    cyRef.current = cy;
    onReady?.(cy);
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [palette, onReady]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    let added = 0;
    cy.batch(() => {
      const wanted = new Set(elements.map((e) => e.data.id as string));
      cy.elements().forEach((el) => {
        if (!wanted.has(el.id())) el.remove();
      });
      for (const el of elements) {
        const existing = cy.getElementById(el.data.id as string);
        if (existing.nonempty()) {
          existing.data(el.data);
          if (el.group === "nodes" && existing.isNode() && (existing.data("parent") ?? null) !== (el.data.parent ?? null)) {
            (existing as unknown as cytoscape.NodeSingular).move({ parent: (el.data.parent as string | undefined) ?? null });
          }
        } else {
          cy.add(el);
          added += 1;
        }
      }
    });
    const unpositioned = cy.nodes().filter((n) => !graph.positions[n.id()] && n.data("kind") !== "cluster");
    if (added > 0 && unpositioned.nonempty()) {
      cy.layout({ name: "dagre", rankDir: "LR", nodeSep: 18, rankSep: 70, fit: true, animate: false } as cytoscape.LayoutOptions).run();
    }
  }, [elements, graph.positions]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.$(":selected").unselect();
    if (selected) cy.getElementById(selected).select();
  }, [selected]);

  return (
    <div className="relative h-full w-full" onContextMenu={(e) => e.preventDefault()}>
      <div ref={container} className="h-full w-full" data-testid="graph-canvas" />
      {Object.keys(graph.nodes).length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center muted pointer-events-none text-sm">
          Search a txid, txid:vout, address or tag to start an investigation.
        </div>
      )}
      {menu && (
        <ul className="absolute panel shadow-lg py-1 text-sm z-10 min-w-56" style={{ left: menu.x, top: menu.y }} role="menu">
          {menuItems(menu.kind).map((item) => (
            <li key={item.action}>
              <button
                role="menuitem"
                className="w-full text-left px-3 py-1 hover:bg-[var(--panel-2)]"
                onClick={() => {
                  setMenu(null);
                  void runMenuAction(item.action, menu.id);
                }}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Run tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: all pass. If `@types/cytoscape-dagre` or the cytoscape typings reject `LayoutOptions` for dagre, keep the `as cytoscape.LayoutOptions` cast shown above rather than using `any`.

```bash
cd /home/fancybear/btc-intel
git add web/src/components/GraphCanvas.tsx web/src/components/StatusBar.tsx web/src/components/StatusBar.test.tsx
git commit -m "feat(web): Cytoscape graph canvas with dagre layout, context menu and status bar

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Search bar and inspector (transaction, address, findings, tagging)

**Files:**
- Create: `web/src/components/SearchBar.tsx`, `web/src/components/Inspector.tsx`
- Test: `web/src/components/Inspector.test.tsx`, `web/src/components/SearchBar.test.tsx`

**Interfaces:**
- Consumes: `api`, the actions, `useWorkbench`, the `Heuristic` and `Category` types, `@tanstack/react-query`.
- Produces:
  - `<SearchBar />`: an input submitted with Enter; when the search returns text tag hits, it lists them and clicking one opens the address.
  - `<Inspector />`: renders from the selected node ID.
    - `tx:`: summary, flags, action buttons (Expand outputs/inputs, Trace forward/backward, Follow peel), findings grouped by heuristic with confidence and a KB link (`#/kb/<kb path>`), fingerprint traits, and input/output tables with labels
    - `addr:`: stats, risk, tags (source, pack, confidence), cluster meta and conflicts, "Expand cluster", the TagEditor form, a recent-transactions list with "Add to graph", and "Watch in case"
    - `script:`: script type and value
  - `findingKbLink(heuristicId, heuristics): string | null`

- [ ] **Step 1: Write the failing tests**

`web/src/components/Inspector.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { txResponse } from "../test/fixtures";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      tx: vi.fn(),
      address: vi.fn(),
      addressTxs: vi.fn(),
      cluster: vi.fn(),
      kb: vi.fn(),
      addTag: vi.fn(),
    },
  };
});
vi.mock("../state/actions", () => ({
  expandOutputs: vi.fn(), expandInputs: vi.fn(), followPeel: vi.fn(), startTrace: vi.fn(),
  expandCluster: vi.fn(), openTx: vi.fn(), addTag: vi.fn(), watchAddress: vi.fn(),
}));

import { api } from "../api/client";
import * as actions from "../state/actions";
import { useWorkbench } from "../state/store";
import Inspector, { findingKbLink } from "./Inspector";

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;
const TXID = "aa".repeat(32);

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  useWorkbench.getState().reset();
  mocked.kb.mockResolvedValue([
    { id: "H-CHG", name: "Change", kb: "heuristics/h-chg.md" },
    { id: "exchange", name: "Exchange", risk: "low", kind: "entity" },
    { id: "perpetrator", name: "Perpetrator", risk: "high", kind: "entity" },
    { id: "theft", name: "Theft", risk: "severe", kind: "abuse" },
  ]);
});

test("findingKbLink resolves heuristic pages", () => {
  const hs = [{ id: "H-CHG", kb: "heuristics/h-chg.md" }] as never;
  expect(findingKbLink("H-CHG", hs)).toBe("#/kb/heuristics/h-chg.md");
  expect(findingKbLink("H-NOPE", hs)).toBeNull();
});

test("transaction inspector shows findings with KB links and runs actions", async () => {
  mocked.tx.mockResolvedValue({
    ...txResponse,
    findings: [{ heuristic: "H-CHG", subject: `out:${TXID}:1`, label: "change", confidence: 0.77, evidence: {} }],
  });
  useWorkbench.getState().select(`tx:${TXID}`);
  wrap(<Inspector />);
  expect(await screen.findByText("change")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "H-CHG" })).toHaveAttribute("href", "#/kb/heuristics/h-chg.md");
  await userEvent.click(screen.getByRole("button", { name: /expand outputs/i }));
  expect(actions.expandOutputs).toHaveBeenCalledWith(TXID);
  expect(screen.getByText("peel_step")).toBeInTheDocument();
});

test("address inspector shows tags and submits the tag form", async () => {
  mocked.address.mockResolvedValue({
    stats: { address: "bc1qdst", tx_count: 2, funded_txo_count: 1, funded_sum: 60_000, spent_txo_count: 0, spent_sum: 0, mempool_tx_count: 0, mempool_delta: 0, balance: 60_000 },
    info: { address: "bc1qdst", tags: [{ id: 1, address: "bc1qdst", label: "Exchange", category: "exchange", abuse: null, actor: null, confidence: "authority_data", confidence_level: 60, source: "https://example.org", pack: "gs:x", is_cluster_definer: false, lastmod: null, created_by: "import" }], cluster: null, category: "exchange", label: "Exchange", risk: "low", stop_category: "exchange" },
    cluster: null,
  });
  mocked.addressTxs.mockResolvedValue({ txs: [], next: null });
  useWorkbench.getState().select("addr:bc1qdst");
  wrap(<Inspector />);
  expect(await screen.findByText("gs:x")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/label/i), "Suspect wallet");
  await userEvent.selectOptions(screen.getByLabelText(/category/i), "perpetrator");
  await userEvent.selectOptions(screen.getByLabelText(/abuse/i), "theft");
  await userEvent.click(screen.getByRole("button", { name: /add tag/i }));
  expect(actions.addTag).toHaveBeenCalledWith(expect.objectContaining({ address: "bc1qdst", label: "Suspect wallet", category: "perpetrator", abuse: "theft" }));
});

test("tag labels are rendered as text, not HTML", async () => {
  mocked.address.mockResolvedValue({
    stats: { address: "bc1qx", tx_count: 0, funded_txo_count: 0, funded_sum: 0, spent_txo_count: 0, spent_sum: 0, mempool_tx_count: 0, mempool_delta: 0, balance: 0 },
    info: { address: "bc1qx", tags: [{ id: 2, address: "bc1qx", label: "<img src=x onerror=alert(1)>", category: "unknown", abuse: null, actor: null, confidence: "unknown", confidence_level: 5, source: "s", pack: "p", is_cluster_definer: false, lastmod: null, created_by: "import" }], cluster: null, category: null, label: null, risk: "none", stop_category: null },
    cluster: null,
  });
  mocked.addressTxs.mockResolvedValue({ txs: [], next: null });
  useWorkbench.getState().select("addr:bc1qx");
  const { container } = wrap(<Inspector />);
  expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  expect(container.querySelector("img")).toBeNull();
});
```

`web/src/components/SearchBar.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../state/actions", () => ({ search: vi.fn(), openAddress: vi.fn() }));

import * as actions from "../state/actions";
import SearchBar from "./SearchBar";

test("submits on Enter and lists tag hits", async () => {
  (actions.search as ReturnType<typeof vi.fn>).mockResolvedValue({
    kind: "text", query: "lazarus",
    tags: [{ id: 1, address: "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", label: "Lazarus Group", category: "individual", abuse: "sanctioned", actor: null, confidence: "authority_data", confidence_level: 60, source: "s", pack: "ofac_sdn", is_cluster_definer: false, lastmod: null, created_by: "import" }],
  });
  render(<SearchBar />);
  await userEvent.type(screen.getByRole("searchbox"), "lazarus{Enter}");
  expect(actions.search).toHaveBeenCalledWith("lazarus");
  await userEvent.click(await screen.findByRole("button", { name: /Lazarus Group/ }));
  expect(actions.openAddress).toHaveBeenCalledWith("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa");
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/components`
Expected: FAIL.

- [ ] **Step 2: Implement SearchBar**

`web/src/components/SearchBar.tsx`:
```tsx
import { useState } from "react";
import type { Tag } from "../api/types";
import { shortAddr } from "../lib/format";
import { openAddress, search } from "../state/actions";

export default function SearchBar() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Tag[]>([]);
  return (
    <div className="relative flex-1 max-w-2xl">
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (!query.trim()) return;
          const res = await search(query.trim());
          setHits(res?.kind === "text" ? res.tags ?? [] : []);
        }}
      >
        <input
          type="search"
          role="searchbox"
          className="input w-full mono"
          placeholder="txid, txid:vout, address, or tag / entity name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>
      {hits.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full panel max-h-80 overflow-auto text-sm">
          {hits.map((t) => (
            <li key={`${t.address}-${t.pack}-${t.label}`}>
              <button
                className="w-full text-left px-3 py-1 hover:bg-[var(--panel-2)]"
                onClick={() => {
                  setHits([]);
                  void openAddress(t.address);
                }}
              >
                {t.label} <span className="muted mono">{shortAddr(t.address)} · {t.category}{t.abuse ? ` / ${t.abuse}` : ""} · {t.pack}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Implement Inspector**

`web/src/components/Inspector.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { AddressResponse, Category, Finding, Heuristic, Tag, TxResponse } from "../api/types";
import { formatBtc, formatTime, shortAddr, shortTxid } from "../lib/format";
import {
  addTag, expandCluster, expandInputs, expandOutputs, followPeel, openTx, startTrace, watchAddress,
} from "../state/actions";
import { useWorkbench } from "../state/store";

export function findingKbLink(heuristicId: string, heuristics: Pick<Heuristic, "id" | "kb">[]): string | null {
  const h = heuristics.find((x) => x.id === heuristicId);
  return h ? `#/kb/${h.kb}` : null;
}

function useCatalog<T>(collection: "heuristics" | "categories") {
  return useQuery({ queryKey: ["kb", collection], queryFn: () => api.kb<T>(collection), staleTime: Infinity });
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-2 text-sm py-0.5">
      <span className="muted">{label}</span>
      <span className="text-right break-all">{children}</span>
    </div>
  );
}

function FindingList({ findings }: { findings: Finding[] }) {
  const heuristics = useCatalog<Heuristic>("heuristics");
  if (!findings.length) return <p className="muted text-sm">No heuristic findings.</p>;
  return (
    <ul className="space-y-1 text-sm">
      {findings.filter((f) => f.heuristic !== "H-FP").map((f, i) => {
        const href = findingKbLink(f.heuristic, heuristics.data ?? []);
        return (
          <li key={`${f.heuristic}-${f.subject}-${i}`} className="border-b border-[var(--border)] pb-1">
            {href ? <a className="mono underline" href={href}>{f.heuristic}</a> : <span className="mono">{f.heuristic}</span>}{" "}
            <strong>{f.label}</strong> <span className="muted">{Math.round(f.confidence * 100)}% · {f.subject.split(":")[0] === "out" ? `output ${f.subject.split(":")[2]}` : "tx"}</span>
          </li>
        );
      })}
    </ul>
  );
}

function TxInspector({ txid }: { txid: string }) {
  const q = useQuery({ queryKey: ["tx", txid], queryFn: () => api.tx(txid) });
  if (q.isLoading) return <p className="muted">Loading transaction…</p>;
  if (q.error || !q.data) return <p className="text-[var(--danger)]">{String(q.error ?? "not found")}</p>;
  const r: TxResponse = q.data;
  const fp = r.findings.find((f) => f.heuristic === "H-FP")?.evidence;
  return (
    <div className="space-y-3">
      <h2 className="font-semibold mono break-all">{txid}</h2>
      <div className="flex flex-wrap gap-1">
        <button className="btn" onClick={() => void expandOutputs(txid)}>Expand outputs</button>
        <button className="btn" onClick={() => void expandInputs(txid)}>Expand inputs</button>
        <button className="btn" onClick={() => void startTrace({ txid }, { direction: "forward" })}>Trace forward</button>
        <button className="btn" onClick={() => void startTrace({ txid }, { direction: "backward" })}>Trace backward</button>
        <button className="btn" onClick={() => void followPeel(txid)}>Follow peel chain</button>
      </div>
      <div>
        <Row label="Block">{r.tx.status.block_height ?? "mempool"} · {formatTime(r.tx.status.block_time)}</Row>
        <Row label="In / out">{formatBtc(r.tx.input_value)} → {formatBtc(r.tx.output_value)}</Row>
        <Row label="Fee">{formatBtc(r.tx.fee)} ({r.tx.feerate} sat/vB)</Row>
        {r.price_usd !== null && <Row label="BTC price then">${r.price_usd.toLocaleString()}</Row>}
        <Row label="Flags">{r.flags.length ? r.flags.map((f) => <span key={f} className="ml-1 mono text-xs">{f}</span>) : "—"}</Row>
      </div>
      <section>
        <h3 className="font-semibold text-sm mb-1">Findings</h3>
        <FindingList findings={r.findings} />
      </section>
      {fp && (
        <section>
          <h3 className="font-semibold text-sm mb-1">Wallet fingerprint</h3>
          {["version", "locktime_kind", "anti_fee_sniping", "rbf", "bip69", "low_r_only", "input_types", "output_types"].map((k) => (
            <Row key={k} label={k}>{JSON.stringify(fp[k])}</Row>
          ))}
        </section>
      )}
      <section>
        <h3 className="font-semibold text-sm mb-1">Inputs</h3>
        {r.tx.vin.map((i) => (
          <Row key={i.n} label={`#${i.n}`}>
            {i.is_coinbase ? "coinbase" : `${r.addresses[i.prevout?.address ?? ""]?.label ?? shortAddr(i.prevout?.address ?? "?")} · ${formatBtc(i.prevout?.value ?? 0)}`}
            {!i.is_coinbase && <button className="ml-2 underline text-xs" onClick={() => void openTx(i.prev_txid)}>open {shortTxid(i.prev_txid)}</button>}
          </Row>
        ))}
        <h3 className="font-semibold text-sm mb-1 mt-2">Outputs</h3>
        {r.tx.vout.map((o) => (
          <Row key={o.n} label={`#${o.n}`}>
            {o.address ? `${r.addresses[o.address]?.label ?? shortAddr(o.address)} · ${formatBtc(o.value)}` : `${o.script_type} · ${formatBtc(o.value)}`}
          </Row>
        ))}
      </section>
    </div>
  );
}

function TagEditor({ address }: { address: string }) {
  const categories = useCatalog<Category>("categories");
  const [label, setLabel] = useState("");
  const [category, setCategory] = useState("perpetrator");
  const [abuse, setAbuse] = useState("");
  const entities = (categories.data ?? []).filter((c) => c.kind === "entity");
  const abuses = (categories.data ?? []).filter((c) => c.kind === "abuse");
  return (
    <form
      className="space-y-1 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (!label.trim()) return;
        void addTag({ address, label: label.trim(), category, abuse: abuse || null });
        setLabel("");
      }}
    >
      <label className="block">Label <input className="input w-full" value={label} onChange={(e) => setLabel(e.target.value)} /></label>
      <label className="block">Category
        <select className="input w-full" value={category} onChange={(e) => setCategory(e.target.value)}>
          {entities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <label className="block">Abuse
        <select className="input w-full" value={abuse} onChange={(e) => setAbuse(e.target.value)}>
          <option value="">—</option>
          {abuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <button className="btn btn-primary" type="submit">Add tag</button>
    </form>
  );
}

function TagList({ tags }: { tags: Tag[] }) {
  if (!tags.length) return <p className="muted text-sm">No attribution tags.</p>;
  return (
    <ul className="text-sm space-y-1">
      {tags.map((t) => (
        <li key={`${t.id}-${t.pack}-${t.label}`} className="border-b border-[var(--border)] pb-1">
          <strong>{t.label}</strong> <span className="muted">{t.category}{t.abuse ? ` / ${t.abuse}` : ""} · {t.confidence} ({t.confidence_level})</span>
          <div className="muted text-xs break-all"><span>{t.pack}</span> · <span>{t.source}</span></div>
        </li>
      ))}
    </ul>
  );
}

function AddressInspector({ address }: { address: string }) {
  const q = useQuery({ queryKey: ["address", address], queryFn: () => api.address(address) });
  const txs = useQuery({ queryKey: ["address-txs", address], queryFn: () => api.addressTxs(address) });
  const caseId = useWorkbench((s) => s.caseId);
  if (q.isLoading) return <p className="muted">Loading address…</p>;
  if (q.error || !q.data) return <p className="text-[var(--danger)]">{String(q.error ?? "not found")}</p>;
  const r: AddressResponse = q.data;
  return (
    <div className="space-y-3">
      <h2 className="font-semibold mono break-all">{address}</h2>
      <div className="flex flex-wrap gap-1">
        <button className="btn" onClick={() => void startTrace({ address }, { direction: "forward" })}>Trace forward</button>
        <button className="btn" onClick={() => void startTrace({ address }, { direction: "backward" })}>Trace backward</button>
        <button className="btn" onClick={() => void expandCluster(address)}>Expand cluster</button>
        <button className="btn" disabled={!caseId} title={caseId ? "" : "Save the case first"} onClick={() => void watchAddress(address)}>Watch in case</button>
      </div>
      <div>
        <Row label="Risk"><span style={{ color: `var(--risk-${r.info.risk})` }}>{r.info.risk}</span></Row>
        <Row label="Balance">{formatBtc(r.stats.balance)}</Row>
        <Row label="Received / sent">{formatBtc(r.stats.funded_sum)} / {formatBtc(r.stats.spent_sum)}</Row>
        <Row label="Transactions">{r.stats.tx_count}</Row>
        {r.cluster && (
          <Row label="Cluster">{shortAddr(r.cluster.root)} · {r.cluster.size} addresses{r.cluster.partial ? " (partial)" : ""}{r.cluster.capped ? " · large service?" : ""}</Row>
        )}
      </div>
      <section>
        <h3 className="font-semibold text-sm mb-1">Tags</h3>
        <TagList tags={r.info.tags} />
      </section>
      <section>
        <h3 className="font-semibold text-sm mb-1">Add tag</h3>
        <TagEditor address={address} />
      </section>
      <section>
        <h3 className="font-semibold text-sm mb-1">Recent transactions</h3>
        {(txs.data?.txs ?? []).map((t) => (
          <Row key={t.txid} label={formatTime(t.block_time)}>
            <span className="mono">{shortTxid(t.txid)}</span> {t.delta !== null && <span>{t.delta >= 0 ? "+" : ""}{formatBtc(t.delta)}</span>}
            <button className="ml-2 underline text-xs" onClick={() => void openTx(t.txid)}>add to graph</button>
          </Row>
        ))}
      </section>
    </div>
  );
}

export default function Inspector() {
  const selected = useWorkbench((s) => s.selected);
  const node = useWorkbench((s) => (s.selected ? s.graph.nodes[s.selected] : undefined));
  if (!selected) return <p className="muted text-sm p-3">Select a node to inspect it. Right-click nodes for actions.</p>;
  const [kind, ...rest] = selected.split(":");
  const value = rest.join(":");
  return (
    <div className="p-3 overflow-auto h-full">
      {kind === "tx" && <TxInspector txid={value} />}
      {kind === "addr" && <AddressInspector address={value} />}
      {kind === "script" && (
        <div className="space-y-1">
          <h2 className="font-semibold">{node?.label ?? "Script output"}</h2>
          <Row label="Value">{formatBtc(Number(node?.data.value ?? 0))}</Row>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add web/src/components/SearchBar.tsx web/src/components/SearchBar.test.tsx web/src/components/Inspector.tsx web/src/components/Inspector.test.tsx
git commit -m "feat(web): search bar and inspector with findings, fingerprint, tags and actions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Trace panel and case panel (with exports)

**Files:**
- Create: `web/src/components/TracePanel.tsx`, `web/src/components/CasePanel.tsx`, `web/src/export/export.ts`
- Test: `web/src/components/TracePanel.test.tsx`, `web/src/export/export.test.ts`

**Interfaces:**
- Consumes: the actions, `useWorkbench`, `api`, the graph model.
- Produces:
  - `<TracePanel />`: a policy form (direction, taint model, hops, min value in BTC, max transactions, max API calls, CoinJoin stop/through, peel mode), Start (seeded from the selected node) and Cancel, and a stops list grouped by reason, where clicking a stop selects its node
  - `buildPolicy(form): Partial<TracePolicy>`, `seedFromNode(id): TraceSeed | null`
  - `<CasePanel onExportPng={() => void} />`: case name, notes, Save/New, the saved-case list (load/delete), watchlist display, and exports (PNG, graph JSON, flows CSV, Markdown report, tags YAML)
  - `edgesCsv(m): string`, `markdownReport(m, meta): string`, `downloadText(filename, text, mime): void`

- [ ] **Step 1: Write the failing tests**

`web/src/export/export.test.ts`:
```ts
import { applyJobEvent, emptyGraph, mergeTx } from "../graph/model";
import { txResponse } from "../test/fixtures";
import { edgesCsv, markdownReport } from "./export";

const TXID = "aa".repeat(32);

test("edgesCsv lists every edge with escaped labels", () => {
  const csv = edgesCsv(mergeTx(emptyGraph(), txResponse)).split("\n");
  expect(csv[0]).toBe("edge_id,direction,txid,index,address,label,value_sats,value_btc,taint_sats");
  expect(csv).toContain(`out:${TXID}:0,out,${TXID},0,bc1qdst,Exchange,60000,0.0006,0`);
  expect(csv.some((l) => l.startsWith(`out:${TXID}:2,out,${TXID},2,,OP_RETURN,0,0,0`))).toBe(true);
});

test("markdownReport summarises exits and labeled addresses", () => {
  let g = mergeTx(emptyGraph(), txResponse);
  g = applyJobEvent(g, { seq: 0, type: "stop", item: { node: "addr:bc1qdst", reason: "labeled", taint: 60_000, detail: "exchange: Exchange" } });
  const md = markdownReport(g, { caseName: "Case | A", notes: "Initial notes", generatedAt: new Date("2026-09-25T12:00:00Z") });
  expect(md).toContain("# Case \\| A");
  expect(md).toContain("- Transactions: 1");
  expect(md).toContain("| labeled | Exchange | exchange | 0.0006 BTC | exchange: Exchange |");
  expect(md).toContain("Traced value reaching labeled exits: 0.0006 BTC");
  expect(md).toContain("## Notes\n\nInitial notes");
});
```

`web/src/components/TracePanel.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../state/actions", () => ({ startTrace: vi.fn(), cancelJob: vi.fn() }));

import * as actions from "../state/actions";
import { useWorkbench } from "../state/store";
import TracePanel, { buildPolicy, seedFromNode } from "./TracePanel";

beforeEach(() => useWorkbench.getState().reset());

test("seedFromNode and buildPolicy", () => {
  expect(seedFromNode(`tx:${"ab".repeat(32)}`)).toEqual({ txid: "ab".repeat(32) });
  expect(seedFromNode("addr:bc1qx")).toEqual({ address: "bc1qx" });
  expect(seedFromNode("script:x:1")).toBeNull();
  expect(buildPolicy({ direction: "backward", taint_model: "fifo", max_hops: "4", min_value_btc: "0.001", max_txs: "50", max_calls: "200", coinjoin: "through", peel_mode: true }))
    .toEqual({ direction: "backward", taint_model: "fifo", max_hops: 4, min_value_sats: 100_000, max_txs: 50, max_calls: 200, coinjoin: "through", peel_mode: true });
});

test("starts a trace from the selected node", async () => {
  useWorkbench.getState().select(`tx:${"ab".repeat(32)}`);
  render(<TracePanel />);
  await userEvent.selectOptions(screen.getByLabelText(/direction/i), "backward");
  await userEvent.click(screen.getByRole("button", { name: /start trace/i }));
  expect(actions.startTrace).toHaveBeenCalledWith({ txid: "ab".repeat(32) }, expect.objectContaining({ direction: "backward", max_hops: 6 }));
});

test("start is disabled without a selection and stops are listed", async () => {
  useWorkbench.getState().updateGraph((g) => ({ ...g, stops: [{ node: "addr:bc1qx", reason: "labeled", taint: 5000, detail: "exchange: X" }] }));
  render(<TracePanel />);
  expect(screen.getByRole("button", { name: /start trace/i })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: /exchange: X/ }));
  expect(useWorkbench.getState().selected).toBe("addr:bc1qx");
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/export src/components/TracePanel.test.tsx`
Expected: FAIL.

- [ ] **Step 2: Implement the exports**

`web/src/export/export.ts`:
```ts
import type { GraphNode } from "../api/types";
import { formatBtc } from "../lib/format";
import { type GraphModel, stats } from "../graph/model";

const csvCell = (v: string | number) => {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
const mdCell = (s: string) => s.replace(/\|/g, "\\|").replace(/\n/g, " ");
const btc = (sats: number) => formatBtc(sats).replace(" BTC", "");

function endpointLabel(node: GraphNode | undefined): { address: string; label: string } {
  if (!node) return { address: "", label: "" };
  if (node.kind === "address") return { address: node.id.slice(5), label: String(node.data.label ?? "") };
  if (node.kind === "script") return { address: "", label: node.label };
  return { address: "", label: "" };
}

export function edgesCsv(m: GraphModel): string {
  const rows = ["edge_id,direction,txid,index,address,label,value_sats,value_btc,taint_sats"];
  for (const e of Object.values(m.edges)) {
    const [direction, txid, index] = e.id.split(":");
    const other = direction === "in" ? m.nodes[e.source] : m.nodes[e.target];
    const { address, label } = endpointLabel(other);
    rows.push([e.id, direction, txid, index, address, label, e.value, btc(e.value), Math.round(e.taint)].map(csvCell).join(","));
  }
  return rows.join("\n");
}

export function markdownReport(m: GraphModel, meta: { caseName: string; notes: string; generatedAt: Date }): string {
  const s = stats(m);
  const order: Record<string, number> = { labeled: 0, coinjoin: 1, unspent: 2 };
  const stops = [...m.stops].sort((a, b) => (order[a.reason] ?? 9) - (order[b.reason] ?? 9) || b.taint - a.taint);
  const labeledValue = stops.filter((x) => x.reason === "labeled").reduce((acc, x) => acc + x.taint, 0);
  const lines = [
    `# ${mdCell(meta.caseName || "Untitled case")}`,
    "",
    `Generated ${meta.generatedAt.toISOString()} by btc-intel.`,
    "",
    "## Summary",
    "",
    `- Transactions: ${s.txs}`,
    `- Addresses: ${s.addresses}`,
    `- Stops recorded: ${s.stops}`,
    `- Traced value reaching labeled exits: ${formatBtc(labeledValue)}`,
    "",
    "## Exits and stops",
    "",
    "| Reason | Node | Category | Traced value | Detail |",
    "|---|---|---|---|---|",
    ...stops.map((x) => {
      const node = m.nodes[x.node];
      const name = node ? node.label : x.node;
      const category = String(node?.data.category ?? "");
      return `| ${x.reason} | ${mdCell(name)} | ${mdCell(category)} | ${formatBtc(x.taint)} | ${mdCell(x.detail)} |`;
    }),
    "",
    "## Labeled addresses",
    "",
    "| Address | Label | Category | Risk |",
    "|---|---|---|---|",
    ...Object.values(m.nodes)
      .filter((n) => n.kind === "address" && n.data.label)
      .map((n) => `| ${n.id.slice(5)} | ${mdCell(String(n.data.label))} | ${mdCell(String(n.data.category ?? ""))} | ${String(n.data.risk ?? "none")} |`),
    "",
    "## Notes",
    "",
    meta.notes || "_No notes._",
    "",
  ];
  return lines.join("\n");
}

export function downloadText(filename: string, text: string, mime = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
```

- [ ] **Step 3: Implement the TracePanel and CasePanel**

`web/src/components/TracePanel.tsx`:
```tsx
import { useState } from "react";
import type { StopReason, TracePolicy, TraceSeed } from "../api/types";
import { btcToSats, formatBtc, shortAddr } from "../lib/format";
import { cancelJob, startTrace } from "../state/actions";
import { useWorkbench } from "../state/store";

export interface PolicyForm {
  direction: "forward" | "backward";
  taint_model: "haircut" | "fifo" | "poison";
  max_hops: string;
  min_value_btc: string;
  max_txs: string;
  max_calls: string;
  coinjoin: "stop" | "through";
  peel_mode: boolean;
}

const DEFAULT_FORM: PolicyForm = {
  direction: "forward", taint_model: "haircut", max_hops: "6", min_value_btc: "0.0001", max_txs: "200",
  max_calls: "600", coinjoin: "stop", peel_mode: false,
};

export function buildPolicy(f: PolicyForm): Partial<TracePolicy> {
  return {
    direction: f.direction, taint_model: f.taint_model, max_hops: Number(f.max_hops),
    min_value_sats: btcToSats(f.min_value_btc) ?? 10_000, max_txs: Number(f.max_txs),
    max_calls: Number(f.max_calls), coinjoin: f.coinjoin, peel_mode: f.peel_mode,
  };
}

export function seedFromNode(id: string | null): TraceSeed | null {
  if (!id) return null;
  const [kind, ...rest] = id.split(":");
  const value = rest.join(":");
  if (kind === "tx") return { txid: value };
  if (kind === "addr") return { address: value };
  return null;
}

const REASONS: StopReason[] = ["labeled", "coinjoin", "unspent", "peel_off", "coinbase", "max_hops", "min_value", "max_txs"];

export default function TracePanel() {
  const [form, setForm] = useState<PolicyForm>(DEFAULT_FORM);
  const selected = useWorkbench((s) => s.selected);
  const job = useWorkbench((s) => s.job);
  const stops = useWorkbench((s) => s.graph.stops);
  const nodes = useWorkbench((s) => s.graph.nodes);
  const select = useWorkbench((s) => s.select);
  const seed = seedFromNode(selected);
  const set = <K extends keyof PolicyForm>(k: K, v: PolicyForm[K]) => setForm((f) => ({ ...f, [k]: v }));
  const field = "block text-sm";
  return (
    <div className="p-3 space-y-3 overflow-auto h-full">
      <p className="text-sm">Seed: {seed ? <span className="mono">{seed.txid ? `tx ${seed.txid.slice(0, 12)}…` : shortAddr(seed.address!)}</span> : <span className="muted">select a transaction or address</span>}</p>
      <div className="grid grid-cols-2 gap-2">
        <label className={field}>Direction
          <select className="input w-full" value={form.direction} onChange={(e) => set("direction", e.target.value as PolicyForm["direction"])}>
            <option value="forward">forward (where did it go?)</option>
            <option value="backward">backward (where from?)</option>
          </select>
        </label>
        <label className={field}>Taint model
          <select className="input w-full" value={form.taint_model} onChange={(e) => set("taint_model", e.target.value as PolicyForm["taint_model"])}>
            <option value="haircut">haircut</option>
            <option value="fifo">FIFO</option>
            <option value="poison">poison</option>
          </select>
        </label>
        <label className={field}>Max hops <input className="input w-full" value={form.max_hops} onChange={(e) => set("max_hops", e.target.value)} /></label>
        <label className={field}>Min value (BTC) <input className="input w-full" value={form.min_value_btc} onChange={(e) => set("min_value_btc", e.target.value)} /></label>
        <label className={field}>Max transactions <input className="input w-full" value={form.max_txs} onChange={(e) => set("max_txs", e.target.value)} /></label>
        <label className={field}>Max API calls <input className="input w-full" value={form.max_calls} onChange={(e) => set("max_calls", e.target.value)} /></label>
        <label className={field}>CoinJoins
          <select className="input w-full" value={form.coinjoin} onChange={(e) => set("coinjoin", e.target.value as PolicyForm["coinjoin"])}>
            <option value="stop">stop at CoinJoin</option>
            <option value="through">continue (probabilistic)</option>
          </select>
        </label>
        <label className="text-sm flex items-center gap-2 mt-5">
          <input type="checkbox" checked={form.peel_mode} onChange={(e) => set("peel_mode", e.target.checked)} /> Peel mode
        </label>
      </div>
      <div className="flex gap-2">
        <button className="btn btn-primary" disabled={!seed} onClick={() => seed && void startTrace(seed, buildPolicy(form))}>Start trace</button>
        <button className="btn" disabled={job?.status !== "running"} onClick={() => void cancelJob()}>Cancel</button>
      </div>
      {job && <p className="text-sm muted">{job.kind} {job.status} · {job.nodes} nodes · {job.stops} stops{job.error ? ` · ${job.error}` : ""}</p>}
      <section>
        <h3 className="font-semibold text-sm mb-1">Stops</h3>
        {REASONS.filter((r) => stops.some((s) => s.reason === r)).map((reason) => (
          <details key={reason} open={reason === "labeled"}>
            <summary className="text-sm cursor-pointer">{reason} ({stops.filter((s) => s.reason === reason).length})</summary>
            <ul className="text-sm">
              {stops.filter((s) => s.reason === reason).sort((a, b) => b.taint - a.taint).slice(0, 200).map((s, i) => (
                <li key={`${s.node}-${i}`}>
                  <button className="underline text-left" onClick={() => select(s.node)}>
                    {s.detail || nodes[s.node]?.label || s.node}
                  </button>{" "}
                  <span className="muted">{formatBtc(s.taint)}</span>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </section>
    </div>
  );
}
```

`web/src/components/CasePanel.tsx`:
```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { toSaved } from "../graph/model";
import { formatTime } from "../lib/format";
import { deleteCase, loadCase, newCase, saveCase } from "../state/actions";
import { useWorkbench } from "../state/store";
import { downloadText, edgesCsv, markdownReport } from "../export/export";

export default function CasePanel({ onExportPng }: { onExportPng: () => void }) {
  const queryClient = useQueryClient();
  const cases = useQuery({ queryKey: ["cases"], queryFn: api.cases });
  const s = useWorkbench();
  const current = useQuery({ queryKey: ["case", s.caseId], queryFn: () => api.getCase(s.caseId!), enabled: !!s.caseId });
  const slug = (s.caseName || "case").replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["cases"] });
  return (
    <div className="p-3 space-y-3 overflow-auto h-full text-sm">
      <label className="block">Case name
        <input className="input w-full" value={s.caseName} onChange={(e) => s.setCaseName(e.target.value)} placeholder="e.g. Bitget hot wallet 2026-09-24" />
      </label>
      <label className="block">Notes
        <textarea className="input w-full h-32" value={s.notes} onChange={(e) => s.setNotes(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={async () => { await saveCase(); await refresh(); }}>{s.dirty ? "Save*" : "Save"}</button>
        <button className="btn" onClick={() => newCase()}>New</button>
        <label className="flex items-center gap-1"><input type="checkbox" checked={s.groupClusters} onChange={(e) => s.setGroupClusters(e.target.checked)} /> group clusters</label>
      </div>
      <section>
        <h3 className="font-semibold mb-1">Export</h3>
        <div className="flex flex-wrap gap-1">
          <button className="btn" onClick={onExportPng}>PNG</button>
          <button className="btn" onClick={() => downloadText(`${slug}.graph.json`, JSON.stringify(toSaved(s.graph), null, 1), "application/json")}>Graph JSON</button>
          <button className="btn" onClick={() => downloadText(`${slug}.flows.csv`, edgesCsv(s.graph), "text/csv")}>Flows CSV</button>
          <button className="btn" onClick={() => downloadText(`${slug}.report.md`, markdownReport(s.graph, { caseName: s.caseName, notes: s.notes, generatedAt: new Date() }), "text/markdown")}>Report (Markdown)</button>
          <button className="btn" onClick={async () => downloadText(`${slug}.tags.yaml`, await api.exportTags("user"), "application/yaml")}>My tags (TagPack)</button>
        </div>
      </section>
      {current.data && current.data.watch.length > 0 && (
        <section>
          <h3 className="font-semibold mb-1">Watchlist</h3>
          <ul className="mono text-xs">{current.data.watch.map((a) => <li key={a}>{a}</li>)}</ul>
        </section>
      )}
      <section>
        <h3 className="font-semibold mb-1">Saved cases</h3>
        <ul className="space-y-1">
          {(cases.data ?? []).map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-2">
              <button className="underline text-left" onClick={() => void loadCase(c.id)}>{c.name}</button>
              <span className="muted text-xs">{c.nodes} nodes · {formatTime(c.updated_at)}</span>
              <button className="btn" aria-label={`delete ${c.name}`} onClick={async () => { await deleteCase(c.id); await refresh(); }}>✕</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Run tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add web/src/components/TracePanel.tsx web/src/components/TracePanel.test.tsx web/src/components/CasePanel.tsx web/src/export
git commit -m "feat(web): trace policy panel, case management and PNG/JSON/CSV/Markdown exports

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Knowledge-base browser and hash routing

**Files:**
- Create: `web/src/lib/route.ts`, `web/src/components/KbBrowser.tsx`
- Test: `web/src/lib/route.test.ts`, `web/src/components/KbBrowser.test.tsx`

**Interfaces:**
- Produces:
  - `Route = { view: "graph" } | { view: "kb"; path: string }`, `parseHash(hash): Route`, `routeToHash(route): string`, `useRoute(): Route`, `navigate(route)`
  - `renderMarkdown(md): string` (DOMPurify-sanitised HTML), `resolveKbLink(currentPath, href): string | null`
  - `<KbBrowser path={string} />`: a navigation list (heuristics by family, techniques by tactic, incidents by date) plus the rendered page. Relative `.md` links navigate within the KB. For incident pages it shows the seeds with an "Open in graph" button.

- [ ] **Step 1: Write the failing tests**

`web/src/lib/route.test.ts`:
```ts
import { parseHash, routeToHash } from "./route";

test("parses graph and kb routes", () => {
  expect(parseHash("")).toEqual({ view: "graph" });
  expect(parseHash("#/graph")).toEqual({ view: "graph" });
  expect(parseHash("#/kb")).toEqual({ view: "kb", path: "index.md" });
  expect(parseHash("#/kb/heuristics/h-cioh.md")).toEqual({ view: "kb", path: "heuristics/h-cioh.md" });
  expect(routeToHash({ view: "kb", path: "incidents/i-2016-bitfinex.md" })).toBe("#/kb/incidents/i-2016-bitfinex.md");
  expect(routeToHash({ view: "graph" })).toBe("#/graph");
});
```

`web/src/components/KbBrowser.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, api: { kb: vi.fn(), kbPage: vi.fn() } };
});
vi.mock("../state/actions", () => ({ openTx: vi.fn(), openAddress: vi.fn() }));

import { api } from "../api/client";
import * as actions from "../state/actions";
import KbBrowser, { renderMarkdown, resolveKbLink } from "./KbBrowser";

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

test("renderMarkdown strips scripts and event handlers", () => {
  const html = renderMarkdown("# T\n\n<script>alert(1)</script><img src=x onerror=alert(1)> [x](javascript:alert(1))");
  expect(html).toContain("<h1");
  expect(html).not.toContain("<script");
  expect(html).not.toContain("onerror");
  expect(html).not.toContain("javascript:");
});

test("resolveKbLink handles relative paths and ignores external links", () => {
  expect(resolveKbLink("heuristics/h-cioh.md", "h-chg.md")).toBe("heuristics/h-chg.md");
  expect(resolveKbLink("heuristics/h-cioh.md", "../incidents/i-2016-bitfinex.md")).toBe("incidents/i-2016-bitfinex.md");
  expect(resolveKbLink("index.md", "ttp-matrix.md")).toBe("ttp-matrix.md");
  expect(resolveKbLink("index.md", "https://example.org")).toBeNull();
  expect(resolveKbLink("index.md", "#section")).toBeNull();
});

test("incident pages list seeds that open in the graph", async () => {
  mocked.kb.mockImplementation(async (c: string) => c === "incidents"
    ? [{ id: "I-2021-COLONIAL", name: "Colonial", date: "2021-05-08", kb: "incidents/i-2021-colonial.md", seeds: [{ kind: "address", value: "bc1qx", role: "seizure", ref: "r", note: "seized" }], seeds_note: null }]
    : []);
  mocked.kbPage.mockResolvedValue({ path: "incidents/i-2021-colonial.md", markdown: "# I-2021-COLONIAL — Colonial\n\nText" });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><KbBrowser path="incidents/i-2021-colonial.md" /></QueryClientProvider>);
  expect(await screen.findByRole("heading", { name: /I-2021-COLONIAL/ })).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: /open bc1qx in graph/i }));
  expect(actions.openAddress).toHaveBeenCalledWith("bc1qx");
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/lib/route.test.ts src/components/KbBrowser.test.tsx`
Expected: FAIL.

- [ ] **Step 2: Implement routing**

`web/src/lib/route.ts`:
```ts
import { useSyncExternalStore } from "react";

export type Route = { view: "graph" } | { view: "kb"; path: string };

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  if (h === "kb" || h.startsWith("kb/")) {
    const path = h.slice(3);
    return { view: "kb", path: path ? decodeURIComponent(path) : "index.md" };
  }
  return { view: "graph" };
}

export function routeToHash(route: Route): string {
  return route.view === "kb" ? `#/kb/${route.path}` : "#/graph";
}

function subscribe(callback: () => void) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash, () => "");
  return parseHash(hash);
}

export function navigate(route: Route) {
  window.location.hash = routeToHash(route);
}
```

- [ ] **Step 3: Implement the KB browser**

`web/src/components/KbBrowser.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import { marked } from "marked";
import type { MouseEvent } from "react";
import { api } from "../api/client";
import type { Heuristic, Incident, Technique } from "../api/types";
import { navigate } from "../lib/route";
import { openAddress, openTx } from "../state/actions";

export function renderMarkdown(md: string): string {
  const html = marked.parse(md, { async: false }) as string;
  return DOMPurify.sanitize(html, { FORBID_TAGS: ["style", "iframe", "form"], FORBID_ATTR: ["style"] });
}

export function resolveKbLink(current: string, href: string): string | null {
  if (!href || href.startsWith("#") || /^[a-z][a-z0-9+.-]*:/i.test(href)) return null;
  const parts = current.split("/").slice(0, -1);
  for (const segment of href.split("#")[0].split("/")) {
    if (segment === "..") parts.pop();
    else if (segment && segment !== ".") parts.push(segment);
  }
  return parts.join("/");
}

function useCollection<T>(name: "heuristics" | "techniques" | "incidents") {
  return useQuery({ queryKey: ["kb", name], queryFn: () => api.kb<T>(name), staleTime: Infinity });
}

function NavLink({ path, label }: { path: string; label: string }) {
  return (
    <li><a className="hover:underline" href={`#/kb/${path}`}>{label}</a></li>
  );
}

export default function KbBrowser({ path }: { path: string }) {
  const heuristics = useCollection<Heuristic>("heuristics");
  const techniques = useCollection<Technique>("techniques");
  const incidents = useCollection<Incident>("incidents");
  const page = useQuery({ queryKey: ["kb-page", path], queryFn: () => api.kbPage(path) });
  const incident = (incidents.data ?? []).find((i) => i.kb === path);

  const onClick = (e: MouseEvent<HTMLElement>) => {
    const anchor = (e.target as HTMLElement).closest("a");
    if (!anchor) return;
    const href = anchor.getAttribute("href") ?? "";
    const internal = resolveKbLink(path, href);
    if (internal && internal.endsWith(".md")) {
      e.preventDefault();
      navigate({ view: "kb", path: internal });
    } else if (/^https?:/i.test(href)) {
      e.preventDefault();
      window.open(href, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="flex h-full min-h-0">
      <nav className="w-72 shrink-0 overflow-auto border-r border-[var(--border)] p-3 text-sm space-y-3">
        <ul><NavLink path="index.md" label="Index" /><NavLink path="ttp-matrix.md" label="TTP matrix" /></ul>
        <div><h3 className="font-semibold">Analysis techniques</h3>
          <ul>{(heuristics.data ?? []).map((h) => <NavLink key={h.id} path={h.kb} label={`${h.parent ? "↳ " : ""}${h.id} ${h.name}`} />)}</ul></div>
        <div><h3 className="font-semibold">Obfuscation & laundering</h3>
          <ul>{(techniques.data ?? []).map((t) => <NavLink key={t.id} path={t.kb} label={`${t.id} ${t.name}`} />)}</ul></div>
        <div><h3 className="font-semibold">Incidents</h3>
          <ul>{[...(incidents.data ?? [])].sort((a, b) => a.date.localeCompare(b.date)).map((i) => <NavLink key={i.id} path={i.kb} label={`${i.date.slice(0, 4)} ${i.name}`} />)}</ul></div>
      </nav>
      <main className="flex-1 overflow-auto p-6">
        {incident && (
          <aside className="panel p-3 mb-4 text-sm">
            <h2 className="font-semibold mb-1">Seeds</h2>
            {incident.seeds.length === 0 && <p className="muted">{incident.seeds_note}</p>}
            <ul>
              {incident.seeds.map((s) => (
                <li key={s.value} className="flex items-center gap-2">
                  <span className="mono break-all">{s.value}</span>
                  <span className="muted">{s.role}{s.note ? ` · ${s.note}` : ""}</span>
                  <button
                    className="btn"
                    aria-label={`open ${s.value} in graph`}
                    onClick={() => {
                      navigate({ view: "graph" });
                      void (s.kind === "tx" ? openTx(s.value) : openAddress(s.value));
                    }}
                  >
                    Open in graph
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        )}
        {page.isLoading && <p className="muted">Loading…</p>}
        {page.error && <p className="text-[var(--danger)]">{String(page.error)}</p>}
        {page.data && (
          <article className="kb-article max-w-3xl" onClick={onClick} dangerouslySetInnerHTML={{ __html: renderMarkdown(page.data.markdown) }} />
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Run tests and typecheck, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npx tsc --noEmit`
Expected: all pass.

```bash
cd /home/fancybear/btc-intel
git add web/src/lib/route.ts web/src/lib/route.test.ts web/src/components/KbBrowser.tsx web/src/components/KbBrowser.test.tsx
git commit -m "feat(web): knowledge-base browser with sanitised Markdown, internal links and incident seeds

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Application shell (layout, tabs, view switching, PNG export)

**Files:**
- Modify: `web/src/App.tsx`, `web/src/App.test.tsx`

**Interfaces:**
- Consumes: every component above, `useRoute`/`navigate`.
- Produces: a header (title, SearchBar, Graph/Knowledge base toggle, API health indicator); the graph view (GraphCanvas plus a right sidebar with Inspector, Trace and Case tabs); the KB view; and the StatusBar. PNG export uses `cy.png({ full: true, scale: 2, output: "blob" })`.

- [ ] **Step 1: Update the failing test**

`web/src/App.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./components/GraphCanvas", () => ({ default: () => <div data-testid="graph-canvas" /> }));
vi.mock("./components/KbBrowser", () => ({ default: ({ path }: { path: string }) => <div>KB {path}</div> }));
vi.mock("./api/client", async () => {
  const actual = await vi.importActual<typeof import("./api/client")>("./api/client");
  return { ...actual, api: { health: vi.fn().mockResolvedValue({ status: "ok", version: "0.1.0" }), kb: vi.fn().mockResolvedValue([]), cases: vi.fn().mockResolvedValue([]) } };
});

import App from "./App";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
}

beforeEach(() => { window.location.hash = ""; });

test("renders the workbench with graph view and tabs", async () => {
  renderApp();
  expect(screen.getByText(/btc-intel workbench/i)).toBeInTheDocument();
  expect(screen.getByTestId("graph-canvas")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Inspector" })).toHaveAttribute("aria-selected", "true");
  await userEvent.click(screen.getByRole("tab", { name: "Trace" }));
  expect(screen.getByRole("button", { name: /start trace/i })).toBeInTheDocument();
  expect(await screen.findByText(/API 0.1.0/)).toBeInTheDocument();
});

test("switches to the knowledge base view", async () => {
  renderApp();
  await userEvent.click(screen.getByRole("button", { name: /knowledge base/i }));
  expect(await screen.findByText("KB index.md")).toBeInTheDocument();
});
```

Run: `cd /home/fancybear/btc-intel/web && npx vitest run src/App.test.tsx`
Expected: FAIL.

- [ ] **Step 2: Implement App**

`web/src/App.tsx`:
```tsx
import { useQuery } from "@tanstack/react-query";
import type { Core } from "cytoscape";
import { useCallback, useRef, useState } from "react";
import { api } from "./api/client";
import CasePanel from "./components/CasePanel";
import GraphCanvas from "./components/GraphCanvas";
import Inspector from "./components/Inspector";
import KbBrowser from "./components/KbBrowser";
import SearchBar from "./components/SearchBar";
import StatusBar from "./components/StatusBar";
import TracePanel from "./components/TracePanel";
import { navigate, useRoute } from "./lib/route";
import { useWorkbench } from "./state/store";

type Tab = "Inspector" | "Trace" | "Case";

export default function App() {
  const route = useRoute();
  const [tab, setTab] = useState<Tab>("Inspector");
  const cyRef = useRef<Core | null>(null);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const caseName = useWorkbench((s) => s.caseName);
  const onReady = useCallback((cy: Core) => { cyRef.current = cy; }, []);

  const exportPng = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#ffffff";
    const blob = cy.png({ full: true, scale: 2, output: "blob", bg }) as unknown as Blob;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(caseName || "graph").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="h-full flex flex-col">
      <header className="flex items-center gap-3 px-4 py-2 border-b border-[var(--border)] bg-[var(--panel)]">
        <span className="font-semibold whitespace-nowrap">btc-intel workbench</span>
        <SearchBar />
        <nav className="flex gap-1">
          <button className={`btn ${route.view === "graph" ? "btn-primary" : ""}`} onClick={() => navigate({ view: "graph" })}>Graph</button>
          <button className={`btn ${route.view === "kb" ? "btn-primary" : ""}`} onClick={() => navigate({ view: "kb", path: "index.md" })}>Knowledge base</button>
        </nav>
        <span className="muted text-xs whitespace-nowrap">
          {health.data ? `API ${health.data.version}` : health.error ? "API offline" : "…"}
        </span>
      </header>
      <div className="flex-1 min-h-0">
        {route.view === "kb" ? (
          <KbBrowser path={route.path} />
        ) : (
          <div className="flex h-full">
            <div className="flex-1 min-w-0">
              <GraphCanvas onReady={onReady} />
            </div>
            <aside className="w-[420px] shrink-0 border-l border-[var(--border)] bg-[var(--panel)] flex flex-col min-h-0">
              <div role="tablist" className="flex border-b border-[var(--border)]">
                {(["Inspector", "Trace", "Case"] as Tab[]).map((t) => (
                  <button
                    key={t}
                    role="tab"
                    aria-selected={tab === t}
                    className={`flex-1 py-2 text-sm ${tab === t ? "font-semibold border-b-2 border-[var(--accent)]" : "muted"}`}
                    onClick={() => setTab(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="flex-1 min-h-0">
                {tab === "Inspector" && <Inspector />}
                {tab === "Trace" && <TracePanel />}
                {tab === "Case" && <CasePanel onExportPng={exportPng} />}
              </div>
            </aside>
          </div>
        )}
      </div>
      <StatusBar />
    </div>
  );
}
```

- [ ] **Step 3: Run the full unit suite, typecheck and build, then commit**

Run: `cd /home/fancybear/btc-intel/web && npx vitest run && npm run build`
Expected: all tests pass, and `web/dist/` is produced without type errors. A bundle-size warning for Cytoscape is acceptable.

```bash
cd /home/fancybear/btc-intel
git add web/src/App.tsx web/src/App.test.tsx
git commit -m "feat(web): application shell with graph/KB views, sidebar tabs and PNG export

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: End-to-end smoke test (Playwright, mocked API) and full-stack verification

**Files:**
- Create: `web/playwright.config.ts`, `web/e2e/fixtures.ts`, `web/e2e/workbench.spec.ts`
- Modify: `README.md` (web workbench usage)

**Interfaces:**
- Consumes: the built app (`npm run build && npm run preview`).
- Produces: `npm run e2e`. It intercepts `/api/**` with in-memory fixtures and exercises this flow: search a txid, render the graph, expand outputs, see findings in the inspector, save a case, reload, load the case, and restore the graph.

- [ ] **Step 1: Install the browser**

Run: `cd /home/fancybear/btc-intel/web && npx playwright install chromium`

If launching later fails with missing system libraries (common on WSL), ask the user to run `! sudo npx playwright install-deps chromium` from `web/`, then re-run the tests.

- [ ] **Step 2: Write the config, fixtures and test**

`web/playwright.config.ts`:
```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:4173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run build && npm run preview -- --strictPort",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
```

`web/e2e/fixtures.ts`:
```ts
import type { Page, Route } from "@playwright/test";

export const TXID = "aa".repeat(32);
export const CHILD = "cc".repeat(32);

function tx(txid: string, inputAddr: string, outputs: [string, number][]) {
  return {
    tx: {
      txid, version: 2, locktime: 0, size: 200, weight: 800, fee: 1000, is_coinbase: false,
      input_value: 100_000, output_value: 99_000, vsize: 200, feerate: 5,
      status: { confirmed: true, block_height: 900000, block_hash: null, block_time: 1749188499 },
      vin: [{ n: 0, prev_txid: "bb".repeat(32), prev_vout: 0, is_coinbase: false, sequence: 4294967293,
        prevout: { n: 0, value: 100_000, script_type: "v0_p2wpkh", address: inputAddr, script_hex: "" },
        scriptsig_hex: "", scriptsig_asm: "", witness: [], inner_redeemscript_asm: null, inner_witnessscript_asm: null }],
      vout: outputs.map(([address, value], n) => ({ n, value, script_type: "v0_p2wpkh", address, script_hex: "" })),
    },
    findings: [{ heuristic: "H-CHG", subject: `out:${txid}:1`, label: "change", confidence: 0.77, evidence: {} }],
    flags: [], price_usd: null, addresses: {},
  };
}

export async function mockApi(page: Page) {
  const cases = new Map<string, Record<string, unknown>>();
  const json = (route: Route, body: unknown, status = 200) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, "");
    const method = route.request().method();
    if (path === "/health") return json(route, { status: "ok", version: "0.1.0" });
    if (path === "/search") return json(route, { kind: "txid", query: url.searchParams.get("q")!.toLowerCase() });
    if (path === `/tx/${TXID}`) return json(route, tx(TXID, "bc1qsource", [["bc1qdest", 60_000], ["bc1qchange", 39_000]]));
    if (path === `/tx/${TXID}/outspends`) return json(route, [{ spent: true, txid: CHILD, vin: 0, status: null }, { spent: false, txid: null, vin: null, status: null }]);
    if (path === `/tx/${CHILD}`) return json(route, tx(CHILD, "bc1qdest", [["bc1qnext", 59_000]]));
    if (path.startsWith("/kb/")) return json(route, path === "/kb/heuristics" ? [{ id: "H-CHG", name: "Change", kb: "heuristics/h-chg.md", parent: null }] : []);
    if (path === "/cases" && method === "GET") return json(route, [...cases.values()].map((c) => ({ id: c.id, name: c.name, created_at: 1, updated_at: 2, nodes: ((c.graph as { nodes?: unknown[] }).nodes ?? []).length })));
    if (path === "/cases" && method === "POST") {
      const body = route.request().postDataJSON();
      const c = { id: "case1", name: body.name, notes: body.notes ?? "", graph: body.graph ?? {}, created_at: 1, updated_at: 2, watch: [] };
      cases.set(c.id, c);
      return json(route, c, 201);
    }
    if (path === "/cases/case1" && method === "GET") return json(route, cases.get("case1"));
    if (path === "/cases/case1" && method === "PUT") {
      const c = { ...cases.get("case1"), ...route.request().postDataJSON() };
      cases.set("case1", c);
      return json(route, c);
    }
    return json(route, { detail: `unmocked ${method} ${path}` }, 404);
  });
}
```

`web/e2e/workbench.spec.ts`:
```ts
import { expect, test } from "@playwright/test";
import { TXID, mockApi } from "./fixtures";

test("search, expand, inspect, save and reload a case", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("searchbox").fill(TXID);
  await page.getByRole("searchbox").press("Enter");
  await expect(page.getByTestId("graph-stats")).toHaveText("1 txs · 3 addresses · 3 edges · 0 stops");
  await expect(page.getByRole("link", { name: "H-CHG" })).toBeVisible();

  await page.getByRole("button", { name: "Expand outputs", exact: true }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText("2 txs · 4 addresses · 5 edges · 0 stops");

  await page.getByRole("tab", { name: "Case" }).click();
  await page.getByLabel("Case name").fill("E2E case");
  await page.getByRole("button", { name: /^Save/ }).click();
  await expect(page.getByRole("button", { name: "E2E case", exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("graph-stats")).toHaveText("0 txs · 0 addresses · 0 edges · 0 stops");
  await page.getByRole("tab", { name: "Case" }).click();
  await page.getByRole("button", { name: "E2E case", exact: true }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText("2 txs · 4 addresses · 5 edges · 0 stops");
});

test("knowledge base view is reachable", async ({ page }) => {
  await mockApi(page);
  await page.goto("/#/kb");
  await expect(page.getByRole("link", { name: "TTP matrix" })).toBeVisible();
});
```

- [ ] **Step 3: Run the end-to-end tests**

Run: `cd /home/fancybear/btc-intel/web && npm run e2e`
Expected: 2 passed.

- [ ] **Step 4: Full-stack manual verification (live, network)**

```bash
cd /home/fancybear/btc-intel/web && npm run build
cd /home/fancybear/btc-intel/backend && uv run btcintel serve
```
Open http://127.0.0.1:8765 in a browser. FastAPI serves the built UI.

Check each of the following:
1. Search `c5908e04daea83ec38101692a0663130bcafa7d0ddaef1fd8821d179d1db1c8c`. The tx appears with 1 input address and 8 output addresses; the inspector shows the fingerprint (v2, locktime zero, no RBF).
2. Right-click the tx and choose "Expand outputs". The spending transactions appear, with status-bar progress while the public API is rate-limited.
3. Open the Trace tab and start a forward trace (max hops 3, max API calls 150). Nodes stream in, and the stops list fills with unspent, labeled and max_hops entries.
4. Search the Blender.io address `3NDzzVxiLBUs1WPvVGRfCYDTAD2Ua2PvW4` (after `import-tags` in Plan 2). The inspector shows GraphSense and OFAC tags with risk **severe**.
5. From the Knowledge base, open an incident with seeds and click "Open in graph".
6. Save the case, reload the page, and load the case. The graph returns with the same layout.
7. Export PNG and the Markdown report, and open both files.

Record any defect found, fix it through a TDD cycle (failing test first) in the relevant task's files, and re-run `npx vitest run`.

- [ ] **Step 5: Document usage and commit**

Append to `README.md`:
```markdown
## Web workbench

    cd web && npm install && npm run build     # production bundle served by the API
    cd ../backend && uv run btcintel serve     # http://127.0.0.1:8765

Development with hot reload: run `uv run btcintel serve` and, in another shell, `cd web && npm run dev`
(http://127.0.0.1:5173, proxies /api to the backend).

- Search a txid, `txid:vout`, address or tag name.
- Right-click nodes to expand inputs/outputs, trace, follow peel chains or expand clusters.
- Save investigations as cases; export PNG, graph JSON, flows CSV, a Markdown report or your tags as a GraphSense TagPack.
- Public Esplora APIs are rate-limited (~1 request/s on mempool.space): large traces take minutes. Set
  `BTCINTEL_BACKENDS` to a self-hosted Esplora/mempool instance and `BTCINTEL_PROXY=socks5h://127.0.0.1:9050`
  to route lookups through Tor.
```

```bash
cd /home/fancybear/btc-intel
git add web/playwright.config.ts web/e2e README.md
git commit -m "test(web): Playwright smoke test with mocked API; document workbench usage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Plan 3 completion checklist

- [ ] `cd web && npx vitest run && npm run build && npm run e2e` all pass.
- [ ] The full-stack manual verification (Task 10 Step 4) was completed against live public APIs, and any issues were fixed test-first.
- [ ] `backend: uv run pytest` still passes (the UI changes do not affect the backend).
