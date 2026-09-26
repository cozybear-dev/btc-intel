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
// Identity of the job subscription allowed to change the graph; a detached one's late events are ignored.
let activeJob: object | null = null;
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

/** Stop applying a job's events to the graph (and optionally cancel it server-side). */
function detachJob(cancel: boolean) {
  const job = st().job;
  if (cancel && job?.status === "running") void api.cancelJob(job.id).catch(() => {});
  unsubscribe?.();
  unsubscribe = null;
  activeJob = null;
  st().setJob(null);
}

function listen(jobId: string, kind: "trace" | "cluster", onDone?: () => Promise<void>) {
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
    detachJob(true);
    const graph = fromSaved(c.graph);
    st().setCase({ id: c.id, name: c.name, notes: c.notes, graph: graph ?? emptyGraph() });
    st().markClean();
    st().setMessage(graph ? null : `Case "${c.name}" graph could not be read (unknown format); starting empty`);
    return c;
  });

export function newCase() {
  detachJob(true);
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
