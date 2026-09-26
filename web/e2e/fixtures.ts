import type { Page, Route } from "@playwright/test";
import { ANALYSED, analysisSections } from "../src/test/fixtures";

export const TXID = "aa".repeat(32);
export const CHILD = "cc".repeat(32);

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
