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
