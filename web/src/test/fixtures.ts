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
