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
export interface Stop { node: string; reason: StopReason; taint: number; detail: string; hops?: number | null }

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
  | { type: "progress"; visited?: number; queued?: number; size?: number; calls?: number; stage?: string }
  | { type: "status"; status: JobStatus; error: string | null }
  | ({ type: "section" } & SectionEvent)
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

export type Depth = "quick" | "deep";
export interface FingerprintSummary { signed_txs: number; signature: string | null; share: number; traits: Record<string, unknown> }
export interface Profile {
  address: string; address_type: string | null; stats: AddressStats; info: AddressInfo;
  txs_seen: number; history_complete: boolean; first_seen: number | null; last_seen: number | null;
  longest_gap_days: number | null; received_txs: number; sent_txs: number; received_external: number;
  reused: boolean; behaviour: Record<string, number>; fingerprint: FingerprintSummary;
}
export interface ClusterSummary {
  root: string; size: number; partial: boolean; capped: boolean;
  conflicts: { labels: string[]; addresses: string[] }[];
  top_labels: { label: string; category: string; abuse: string | null; count: number }[];
  calls_used: number; error: string | null;
}
export type BucketKind = "labeled" | "own_cluster" | "coinjoin" | "unspent" | "coinbase" | "limits" | "remainder";
export interface Bucket {
  kind: BucketKind; key: string; label: string; risk: RiskLevel; source: string | null;
  amount: number; share: number; min_hops: number | null; nodes: string[];
}
export interface Exposure {
  direction: "backward" | "forward"; total: number; buckets: Bucket[]; resolved_share: number;
  incomplete: boolean; reason: string | null; calls_used: number; error: string | null;
}
export interface Reason { level: RiskLevel; rule: string; text: string }
export interface Verdict { level: RiskLevel; final: boolean; low_confidence: boolean; coverage: string; reasons: Reason[] }
export interface AnalysisSections {
  profile?: Profile; cluster?: ClusterSummary; sources?: Exposure; destinations?: Exposure; verdict?: Verdict;
}
export type SectionEvent =
  | { name: "profile"; data: Profile }
  | { name: "cluster"; data: ClusterSummary }
  | { name: "sources"; data: Exposure }
  | { name: "destinations"; data: Exposure }
  | { name: "verdict"; data: Verdict };
export interface AnalysisReport {
  address: string; depth: Depth; generated_at: number; profile: Profile; cluster: ClusterSummary | null;
  sources: Exposure | null; destinations: Exposure | null; verdict: Verdict; calls_used: number; markdown: string;
}
