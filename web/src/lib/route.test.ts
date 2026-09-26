import { parseHash, routeToHash } from "./route";

test("parses graph and kb routes", () => {
  expect(parseHash("")).toEqual({ view: "graph" });
  expect(parseHash("#/graph")).toEqual({ view: "graph" });
  expect(parseHash("#/kb")).toEqual({ view: "kb", path: "index.md" });
  expect(parseHash("#/kb/heuristics/h-cioh.md")).toEqual({ view: "kb", path: "heuristics/h-cioh.md" });
  expect(routeToHash({ view: "kb", path: "incidents/i-2016-bitfinex.md" })).toBe("#/kb/incidents/i-2016-bitfinex.md");
  expect(routeToHash({ view: "graph" })).toBe("#/graph");
});

test("parses the analysis route", () => {
  expect(parseHash("#/analysis/bc1qxyz")).toEqual({ view: "analysis", address: "bc1qxyz" });
  expect(parseHash("#/analysis/")).toEqual({ view: "graph" });
  expect(routeToHash({ view: "analysis", address: "bc1qxyz" })).toBe("#/analysis/bc1qxyz");
});
