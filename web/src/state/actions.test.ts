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
      analyze: vi.fn(), job: vi.fn(),
    },
  };
});

import { ApiError, api } from "../api/client";
import * as actions from "./actions";
import { useWorkbench } from "./store";
import { emptyGraph, toSaved } from "../graph/model";

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

test("loading a case detaches a running trace so its events cannot leak into that case", async () => {
  mocked.startTrace.mockResolvedValue({ job_id: "j9" });
  await actions.startTrace({ txid: TXID }, { max_hops: 2 });
  const oldJobEvent = handlers.onEvent!;
  mocked.cancelJob.mockResolvedValue({ cancelled: true });
  mocked.getCase.mockResolvedValue({ id: "k3", name: "Other", notes: "", graph: toSaved(emptyGraph()), created_at: 1, updated_at: 2, watch: [] });
  await actions.loadCase("k3");
  oldJobEvent({ seq: 0, type: "nodes", items: [{ id: "addr:leak", kind: "address", label: "leak", data: {} }] });
  const s = useWorkbench.getState();
  expect(s.graph.nodes["addr:leak"]).toBeUndefined();
  expect(s.dirty).toBe(false);
  expect(s.job).toBeNull();
  expect(mocked.cancelJob).toHaveBeenCalledWith("j9");
});

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
  expect(useWorkbench.getState().job).toMatchObject({ stages: ["cluster"], finished: null });
  emit({ seq: 3, type: "done", incomplete: false, reason: null, calls_used: 40 });
  emit({ seq: 4, type: "status", status: "done", error: null });
  await vi.waitFor(() => expect(useWorkbench.getState().analysis?.markdown).toBe("# Address analysis"));
  const s = useWorkbench.getState();
  expect(s.analysis?.sections.verdict?.level).toBe("severe");
  expect(s.graph.nodes["addr:bc1qaddr"]).toBeDefined();
  expect(s.job).toMatchObject({ kind: "analysis", status: "done", calls: 40, nodes: 1, stages: ["cluster"] });
  expect(s.job!.finished).toBeGreaterThanOrEqual(s.job!.started);
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

test("edits or notes on top of an analysis count as unsaved work", async () => {
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  mocked.analyze.mockResolvedValue({ job_id: "a5" });
  await actions.startAnalysis("bc1qaddr");
  handlers.onEvent!({ seq: 0, type: "nodes", items: [{ id: "addr:bc1qaddr", kind: "address", label: "a", data: {} }] });
  expect(actions.hasUnsavedWork()).toBe(false); // job events alone are regenerable
  useWorkbench.getState().setNotes("suspect: exchange deposit");
  expect(actions.hasUnsavedWork()).toBe(true);
  expect(await actions.startAnalysis("bc1qother")).toBe(false);
  expect(confirm).toHaveBeenCalledTimes(1);
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
