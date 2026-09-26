import type { ElementDefinition } from "cytoscape";
import type { RiskLevel } from "../api/types";
import { formatBtc, shortAddr } from "../lib/format";
import { type GraphModel, stopsByNode } from "./model";

export interface Palette {
  text: string;
  muted: string;
  border: string;
  accent: string;
  tx: string;
  script: string;
  taint: string;
  risk: Record<RiskLevel, string>;
}

export const LIGHT: Palette = {
  text: "#1b1b1f", muted: "#5f6368", border: "#dedede", accent: "#2f6fed", tx: "#6b5bd6", script: "#9aa0a6",
  taint: "#e0662e",
  risk: { none: "#8a8f98", low: "#2e9d5b", medium: "#c98f00", high: "#e0662e", severe: "#d13a3a" },
};

export const DARK: Palette = {
  text: "#e8eaed", muted: "#9aa0a6", border: "#2d3139", accent: "#6ea0ff", tx: "#9a8cff", script: "#7d838c",
  taint: "#ff8a4c",
  risk: { none: "#8a8f98", low: "#4cc07e", medium: "#e6b422", high: "#ff8a4c", severe: "#ff5c5c" },
};

export function currentPalette(): Palette {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches ? DARK : LIGHT;
}

export function edgeWidth(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const w = 1 + 1.5 * Math.log10(Math.max(1, value / 100_000));
  return Math.min(10, Math.max(1, Number(w.toFixed(2))));
}

export interface StyleBlock { selector: string; style: Record<string, string | number> }

export function buildStylesheet(p: Palette): StyleBlock[] {
  return [
    { selector: "node", style: { label: "data(label)", "font-size": 10, color: p.text, "text-valign": "bottom", "text-margin-y": 4, "text-wrap": "ellipsis", "text-max-width": "140px" } },
    { selector: 'node[kind = "address"]', style: { shape: "ellipse", width: 26, height: 26, "background-color": "data(color)", "border-width": 1, "border-color": p.border } },
    { selector: 'node[kind = "tx"]', style: { shape: "round-rectangle", width: 18, height: 18, "background-color": p.tx } },
    { selector: 'node[kind = "script"]', style: { shape: "diamond", width: 14, height: 14, "background-color": p.script } },
    { selector: "node[?coinjoin]", style: { "border-width": 4, "border-color": p.risk.medium, "border-style": "double" } },
    { selector: "node[stop]", style: { "border-width": 3, "border-color": p.accent } },
    { selector: ":parent", style: { "background-opacity": 0.06, "border-color": p.muted, "border-style": "dashed", "text-valign": "top", "text-halign": "center" } },
    { selector: "edge", style: { width: "data(width)", "line-color": p.muted, "target-arrow-color": p.muted, "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.8, label: "data(amount)", "font-size": 8, color: p.muted, "text-rotation": "autorotate" } },
    { selector: "edge[taint > 0]", style: { "line-color": p.taint, "target-arrow-color": p.taint } },
    { selector: ":selected", style: { "overlay-color": p.accent, "overlay-opacity": 0.25, "overlay-padding": 6 } },
  ];
}

export function toElements(m: GraphModel, p: Palette, opts: { groupClusters: boolean }): ElementDefinition[] {
  const hidden = new Set(m.hidden);
  const stops = stopsByNode(m);
  const visible = Object.values(m.nodes).filter((n) => !hidden.has(n.id));
  const clusterSize = new Map<string, number>();
  if (opts.groupClusters) {
    for (const n of visible) {
      const c = n.kind === "address" ? (n.data.cluster as string | null) : null;
      if (c) clusterSize.set(c, (clusterSize.get(c) ?? 0) + 1);
    }
  }
  const els: ElementDefinition[] = [];
  for (const [root, count] of clusterSize) {
    if (count >= 2) els.push({ group: "nodes", data: { id: `cluster:${root}`, label: `cluster ${shortAddr(root)} (${count})`, kind: "cluster" } });
  }
  for (const n of visible) {
    const cluster = n.kind === "address" ? (n.data.cluster as string | null) : null;
    const flags = (n.data.flags as string[] | undefined) ?? [];
    const risk = (n.data.risk as RiskLevel | undefined) ?? "none";
    els.push({
      group: "nodes",
      data: {
        id: n.id, label: n.label, kind: n.kind, risk,
        color: n.kind === "address" ? p.risk[risk] ?? p.risk.none : undefined,
        coinjoin: flags.some((f) => f.startsWith("coinjoin:")) || undefined,
        stop: stops.get(n.id)?.join(","),
        parent: cluster && (clusterSize.get(cluster) ?? 0) >= 2 ? `cluster:${cluster}` : undefined,
      },
      position: m.positions[n.id] ? { ...m.positions[n.id] } : undefined,
    });
  }
  for (const e of Object.values(m.edges)) {
    if (hidden.has(e.source) || hidden.has(e.target) || !m.nodes[e.source] || !m.nodes[e.target]) continue;
    els.push({ group: "edges", data: { id: e.id, source: e.source, target: e.target, value: e.value, taint: e.taint, width: edgeWidth(e.value), amount: formatBtc(e.value) } });
  }
  return els;
}
