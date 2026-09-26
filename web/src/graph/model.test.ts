import { TXID, txResponse } from "../test/fixtures";
import {
  addEdges, addNodes, addTagToNode, applyJobEvent, emptyGraph, fromSaved, hideNodes, mergeTrace, mergeTx,
  removeNode, setClusterForAddresses, setPositions, stats, stopsByNode, toSaved,
} from "./model";


test("mergeTx builds a bipartite graph with script nodes", () => {
  const g = mergeTx(emptyGraph(), txResponse);
  expect(stats(g)).toEqual({ txs: 1, addresses: 3, scripts: 1, edges: 4, stops: 0 });
  expect(g.nodes[`tx:${TXID}`].data.flags).toEqual(["peel_step"]);
  expect(g.nodes["addr:bc1qdst"].label).toBe("Exchange");
  expect(g.edges[`in:${TXID}:0`]).toMatchObject({ source: "addr:bc1qsrc", target: `tx:${TXID}`, value: 100_000 });
  expect(g.edges[`out:${TXID}:2`].target).toBe(`script:${TXID}:2`);
});

test("merging keeps existing taint and positions", () => {
  let g = mergeTx(emptyGraph(), txResponse);
  g = addEdges(g, [{ ...g.edges[`out:${TXID}:0`], taint: 5000 }]);
  g = setPositions(g, { "addr:bc1qdst": { x: 10, y: 20 } });
  g = mergeTx(g, txResponse);
  expect(g.edges[`out:${TXID}:0`].taint).toBe(5000);
  expect(g.positions["addr:bc1qdst"]).toEqual({ x: 10, y: 20 });
});

test("applyJobEvent keeps hidden and positions", () => {
  let g = hideNodes(mergeTx(emptyGraph(), txResponse), ["addr:bc1qchg"]);
  g = setPositions(g, { [`tx:${TXID}`]: { x: 1, y: 2 } });
  g = applyJobEvent(g, { seq: 0, type: "nodes", items: [{ id: "addr:new", kind: "address", label: "new", data: {} }] });
  g = applyJobEvent(g, { seq: 1, type: "edges", items: [{ id: "out:x:0", source: `tx:${TXID}`, target: "addr:new", value: 5, taint: 5 }] });
  g = applyJobEvent(g, { seq: 2, type: "stop", item: { node: "addr:new", reason: "unspent", taint: 5, detail: "" } });
  expect(g.hidden).toEqual(["addr:bc1qchg"]);
  expect(g.positions[`tx:${TXID}`]).toEqual({ x: 1, y: 2 });
  expect(stopsByNode(g).get("addr:new")).toEqual(["unspent"]);
  expect(applyJobEvent(g, { seq: 3, type: "status", status: "done", error: null })).toBe(g);
});

test("mergeTrace merges nodes, edges and stops", () => {
  const g = mergeTrace(emptyGraph(), {
    seed: { txid: TXID }, policy: {} as never, incomplete: false, reason: null, calls_used: 3, txs_expanded: 1,
    nodes: [{ id: `tx:${TXID}`, kind: "tx", label: "aa", data: {} }],
    edges: [], stops: [{ node: `tx:${TXID}`, reason: "coinjoin", taint: 1, detail: "whirlpool" }],
  });
  expect(stats(g).stops).toBe(1);
});

test("removeNode drops incident edges; hide/show", () => {
  const g = removeNode(mergeTx(emptyGraph(), txResponse), `tx:${TXID}`);
  expect(stats(g).edges).toBe(0);
  expect(hideNodes(emptyGraph(), ["a", "a"]).hidden).toEqual(["a"]);
});

test("cluster and tag updates", () => {
  let g = mergeTx(emptyGraph(), txResponse);
  g = setClusterForAddresses(g, new Set(["bc1qsrc", "bc1qchg", "absent"]), "bc1qsrc");
  expect(g.nodes["addr:bc1qchg"].data.cluster).toBe("bc1qsrc");
  g = addTagToNode(g, "addr:bc1qchg", {
    id: 1, address: "bc1qchg", label: "Suspect", category: "perpetrator", abuse: "theft", actor: null,
    confidence: "forensic_investigation", confidence_level: 70, source: "analyst", pack: "user",
    is_cluster_definer: false, lastmod: null, created_by: "analyst",
  }, "severe");
  expect(g.nodes["addr:bc1qchg"].label).toBe("Suspect");
  expect(g.nodes["addr:bc1qchg"].data.risk).toBe("severe");
});

test("save/load roundtrip", () => {
  const g = setPositions(mergeTx(emptyGraph(), txResponse), { [`tx:${TXID}`]: { x: 3, y: 4 } });
  expect(fromSaved(JSON.parse(JSON.stringify(toSaved(g))))).toEqual(g);
});

test("fromSaved rejects unknown shapes", () => {
  expect(fromSaved({})).toBeNull();
  expect(fromSaved({ version: 2, nodes: [] })).toBeNull();
  expect(fromSaved(null)).toBeNull();
  expect(fromSaved({ version: 1, nodes: "x", edges: [], stops: [], hidden: [], positions: {} })).toBeNull();
});

test("addNodes merges data", () => {
  const g = addNodes(addNodes(emptyGraph(), [{ id: "n", kind: "address", label: "n", data: { a: 1 } }]),
    [{ id: "n", kind: "address", label: "n2", data: { b: 2 } }]);
  expect(g.nodes.n).toEqual({ id: "n", kind: "address", label: "n2", data: { a: 1, b: 2 } });
});
