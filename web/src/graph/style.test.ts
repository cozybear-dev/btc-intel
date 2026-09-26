import { emptyGraph, hideNodes, mergeTx, setClusterForAddresses } from "./model";
import { txResponse } from "../test/fixtures";
import { LIGHT, buildStylesheet, edgeWidth, toElements } from "./style";

test("edgeWidth is bounded", () => {
  expect(edgeWidth(0)).toBe(1);
  expect(edgeWidth(100_000)).toBe(1);
  expect(edgeWidth(100_000_000)).toBe(5.5);
  expect(edgeWidth(2_100_000_000_000_000)).toBe(10);
  expect(edgeWidth(Number.NaN)).toBe(1);
});

test("toElements colours addresses by risk and skips hidden", () => {
  const g = hideNodes(mergeTx(emptyGraph(), txResponse), ["addr:bc1qchg"]);
  const els = toElements(g, LIGHT, { groupClusters: false });
  const dst = els.find((e) => e.data.id === "addr:bc1qdst")!;
  expect(dst.data.color).toBe(LIGHT.risk.low);
  expect(els.some((e) => e.data.id === "addr:bc1qchg")).toBe(false);
  expect(els.some((e) => e.data.target === "addr:bc1qchg")).toBe(false);
  const edge = els.find((e) => e.data.id === `out:${"aa".repeat(32)}:0`)!;
  expect(edge.data.amount).toBe("0.0006 BTC");
});

test("clusters become compound parents when grouping", () => {
  const g = setClusterForAddresses(mergeTx(emptyGraph(), txResponse), new Set(["bc1qsrc", "bc1qchg"]), "bc1qsrc");
  const els = toElements(g, LIGHT, { groupClusters: true });
  expect(els[0].data.id).toBe("cluster:bc1qsrc");
  expect(els.find((e) => e.data.id === "addr:bc1qchg")!.data.parent).toBe("cluster:bc1qsrc");
  expect(toElements(g, LIGHT, { groupClusters: false }).some((e) => e.data.id === "cluster:bc1qsrc")).toBe(false);
});

test("stylesheet has selectors for every node kind", () => {
  const selectors = buildStylesheet(LIGHT).map((b) => b.selector);
  expect(selectors).toEqual(expect.arrayContaining(['node[kind = "address"]', 'node[kind = "tx"]', 'node[kind = "script"]', "edge"]));
});
