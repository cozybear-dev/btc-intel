import type { GraphNode } from "../api/types";
import { formatBtc } from "../lib/format";
import { type GraphModel, stats } from "../graph/model";

const csvCell = (v: string | number) => {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
const mdCell = (s: string) => s.replace(/\|/g, "\\|").replace(/\n/g, " ");
const btc = (sats: number) => formatBtc(sats).replace(" BTC", "");

function endpointLabel(node: GraphNode | undefined): { address: string; label: string } {
  if (!node) return { address: "", label: "" };
  if (node.kind === "address") return { address: node.id.slice(5), label: String(node.data.label ?? "") };
  if (node.kind === "script") return { address: "", label: node.label };
  return { address: "", label: "" };
}

export function edgesCsv(m: GraphModel): string {
  const rows = ["edge_id,direction,txid,index,address,label,value_sats,value_btc,taint_sats"];
  for (const e of Object.values(m.edges)) {
    const [direction, txid, index] = e.id.split(":");
    const other = direction === "in" ? m.nodes[e.source] : m.nodes[e.target];
    const { address, label } = endpointLabel(other);
    rows.push([e.id, direction, txid, index, address, label, e.value, btc(e.value), Math.round(e.taint)].map(csvCell).join(","));
  }
  return rows.join("\n");
}

export function markdownReport(m: GraphModel, meta: { caseName: string; notes: string; generatedAt: Date }): string {
  const s = stats(m);
  const order: Record<string, number> = { labeled: 0, coinjoin: 1, unspent: 2 };
  const stops = [...m.stops].sort((a, b) => (order[a.reason] ?? 9) - (order[b.reason] ?? 9) || b.taint - a.taint);
  const labeledValue = stops.filter((x) => x.reason === "labeled").reduce((acc, x) => acc + x.taint, 0);
  const lines = [
    `# ${mdCell(meta.caseName || "Untitled case")}`,
    "",
    `Generated ${meta.generatedAt.toISOString()} by btc-intel.`,
    "",
    "## Summary",
    "",
    `- Transactions: ${s.txs}`,
    `- Addresses: ${s.addresses}`,
    `- Stops recorded: ${s.stops}`,
    `- Traced value reaching labeled exits: ${formatBtc(labeledValue)}`,
    "",
    "## Exits and stops",
    "",
    "| Reason | Node | Category | Traced value | Detail |",
    "|---|---|---|---|---|",
    ...stops.map((x) => {
      const node = m.nodes[x.node];
      const name = node ? node.label : x.node;
      const category = String(node?.data.category ?? "");
      return `| ${x.reason} | ${mdCell(name)} | ${mdCell(category)} | ${formatBtc(x.taint)} | ${mdCell(x.detail)} |`;
    }),
    "",
    "## Labeled addresses",
    "",
    "| Address | Label | Category | Risk |",
    "|---|---|---|---|",
    ...Object.values(m.nodes)
      .filter((n) => n.kind === "address" && n.data.label)
      .map((n) => `| ${n.id.slice(5)} | ${mdCell(String(n.data.label))} | ${mdCell(String(n.data.category ?? ""))} | ${String(n.data.risk ?? "none")} |`),
    "",
    "## Notes",
    "",
    meta.notes || "_No notes._",
    "",
  ];
  return lines.join("\n");
}

export function downloadText(filename: string, text: string, mime = "text/plain"): void {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
