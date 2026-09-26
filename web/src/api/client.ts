import type {
  AddressResponse, AddressTxsResponse, Case, CaseSummary, ClusterResponse, Depth, JobInfo, NewTag, Outspend,
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
  analyze: (address: string, depth: Depth = "quick") => request<{ job_id: string }>("/analyze", post({ address, depth })),
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
