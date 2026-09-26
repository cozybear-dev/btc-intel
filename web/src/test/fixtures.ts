import type { AnalysisSections, TxResponse } from "../api/types";

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

export const ANALYSED = "bc1qanalysed";
export const RANSOM = "bc1qransom";

export const analysisSections: AnalysisSections = {
  verdict: {
    level: "severe", final: true, low_confidence: false,
    coverage: "Traced 100% of funds to an endpoint within 3 hops; 0.0% not reached",
    reasons: [
      { level: "severe", rule: "direct_severe", text: "Received 0.015 BTC directly from LockBit (ransomware, ransomwhere)" },
      { level: "low", rule: "low_only", text: "Outgoing funds went to only low-risk known entities: Example Exchange" },
    ],
  },
  profile: {
    address: ANALYSED, address_type: "v0_p2wpkh",
    stats: { address: ANALYSED, tx_count: 2, funded_txo_count: 1, funded_sum: 1_500_000, spent_txo_count: 1, spent_sum: 1_500_000, mempool_tx_count: 0, mempool_delta: 0, balance: 0 },
    info: { address: ANALYSED, tags: [], cluster: null, category: null, label: null, risk: "none", stop_category: null },
    txs_seen: 2, history_complete: true, first_seen: 1_700_000_000, last_seen: 1_700_086_400, longest_gap_days: 1,
    received_txs: 1, sent_txs: 1, received_external: 1_500_000, reused: false, behaviour: { peel_step: 1 },
    fingerprint: { signed_txs: 1, signature: "v2|lt:zero|rbf:1|in:v0_p2wpkh", share: 1, traits: {} },
  },
  cluster: { root: ANALYSED, size: 1, partial: false, capped: false, conflicts: [], top_labels: [], calls_used: 1, error: null },
  sources: {
    direction: "backward", total: 1_500_000, resolved_share: 1, incomplete: false, reason: null, calls_used: 3, error: null,
    buckets: [{ kind: "labeled", key: "ransomware", label: "LockBit", risk: "severe", source: "ransomwhere", amount: 1_500_000, share: 1, min_hops: 1, nodes: [`addr:${RANSOM}`] }],
  },
  destinations: {
    direction: "forward", total: 1_500_000, resolved_share: 0.999, incomplete: false, reason: null, calls_used: 4, error: null,
    buckets: [
      { kind: "labeled", key: "exchange", label: "Example Exchange", risk: "low", source: "test", amount: 1_000_000, share: 0.6667, min_hops: 1, nodes: ["addr:bc1qexchange"] },
      { kind: "unspent", key: "unspent", label: "Still unspent", risk: "none", source: null, amount: 499_000, share: 0.3327, min_hops: 1, nodes: ["addr:bc1qunspent"] },
      { kind: "remainder", key: "remainder", label: "Fees or not reached (budget)", risk: "none", source: null, amount: 1_000, share: 0.0007, min_hops: null, nodes: [] },
    ],
  },
};
