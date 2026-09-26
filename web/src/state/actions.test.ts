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
