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
