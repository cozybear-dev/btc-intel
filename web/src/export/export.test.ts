import { applyJobEvent, emptyGraph, mergeTx } from "../graph/model";
import { txResponse } from "../test/fixtures";
import { MAX_PNG_SIDE, edgesCsv, exportPng, markdownReport } from "./export";

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

test("exportPng caps the canvas size and refuses to save an empty image", () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:png"), revokeObjectURL: vi.fn() });
  const image = () => new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" });
  const fakeCy = (w: number, h: number) => {
    const png = vi.fn().mockImplementation(image);
    return { png, elements: () => ({ boundingBox: () => ({ w, h }) }) };
  };
  // cytoscape ignores maxWidth/maxHeight when scale is given, so the scale itself must bound the canvas
  const tall = fakeCy(1_200, 110_000);
  expect(exportPng(tall as never, "case.png", "#fff")).toBe(true);
  const opts = tall.png.mock.calls[0][0];
  expect(opts).toMatchObject({ full: true, output: "blob", bg: "#fff" });
  expect(110_000 * opts.scale).toBeLessThanOrEqual(MAX_PNG_SIDE);
  expect(1_200 * opts.scale).toBeGreaterThan(0);
  const small = fakeCy(500, 400);
  exportPng(small as never, "case.png", "#fff");
  expect(small.png.mock.calls[0][0].scale).toBe(2);
  expect(click).toHaveBeenCalledTimes(2);
  // browsers return an empty image when the canvas exceeds their size limit
  const empty = fakeCy(500, 400);
  empty.png.mockReturnValue(new Blob([]));
  expect(exportPng(empty as never, "case.png", "#fff")).toBe(false);
  expect(click).toHaveBeenCalledTimes(2);
  click.mockRestore();
});
