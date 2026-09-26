import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { AddressResponse, Category, Finding, Heuristic, Tag, TxResponse } from "../api/types";
import { formatBtc, formatTime, shortAddr, shortTxid } from "../lib/format";
import {
  addTag, expandCluster, expandInputs, expandOutputs, followPeel, openTx, startTrace, watchAddress,
} from "../state/actions";
import { useWorkbench } from "../state/store";

export function findingKbLink(heuristicId: string, heuristics: Pick<Heuristic, "id" | "kb">[]): string | null {
  const h = heuristics.find((x) => x.id === heuristicId);
  return h ? `#/kb/${h.kb}` : null;
}

function useCatalog<T>(collection: "heuristics" | "categories") {
  return useQuery({ queryKey: ["kb", collection], queryFn: () => api.kb<T>(collection), staleTime: Infinity });
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-2 text-sm py-0.5">
      <span className="muted">{label}</span>
      <span className="text-right break-all">{children}</span>
    </div>
  );
}

function FindingList({ findings }: { findings: Finding[] }) {
  const heuristics = useCatalog<Heuristic>("heuristics");
  if (!findings.length) return <p className="muted text-sm">No heuristic findings.</p>;
  return (
    <ul className="space-y-1 text-sm">
      {findings.filter((f) => f.heuristic !== "H-FP").map((f, i) => {
        const href = findingKbLink(f.heuristic, heuristics.data ?? []);
        return (
          <li key={`${f.heuristic}-${f.subject}-${i}`} className="border-b border-[var(--border)] pb-1">
            {href ? <a className="mono underline" href={href}>{f.heuristic}</a> : <span className="mono">{f.heuristic}</span>}{" "}
            <strong>{f.label}</strong> <span className="muted">{Math.round(f.confidence * 100)}% · {f.subject.split(":")[0] === "out" ? `output ${f.subject.split(":")[2]}` : "tx"}</span>
          </li>
        );
      })}
    </ul>
  );
}

function TxInspector({ txid }: { txid: string }) {
  const q = useQuery({ queryKey: ["tx", txid], queryFn: () => api.tx(txid) });
  if (q.isLoading) return <p className="muted">Loading transaction…</p>;
  if (q.error || !q.data) return <p className="text-[var(--danger)]">{String(q.error ?? "not found")}</p>;
  const r: TxResponse = q.data;
  const fp = r.findings.find((f) => f.heuristic === "H-FP")?.evidence;
  return (
    <div className="space-y-3">
      <h2 className="font-semibold mono break-all">{txid}</h2>
      <div className="flex flex-wrap gap-1">
        <button className="btn" onClick={() => void expandOutputs(txid)}>Expand outputs</button>
        <button className="btn" onClick={() => void expandInputs(txid)}>Expand inputs</button>
        <button className="btn" onClick={() => void startTrace({ txid }, { direction: "forward" })}>Trace forward</button>
        <button className="btn" onClick={() => void startTrace({ txid }, { direction: "backward" })}>Trace backward</button>
        <button className="btn" onClick={() => void followPeel(txid)}>Follow peel chain</button>
      </div>
      <div>
        <Row label="Block">{r.tx.status.block_height ?? "mempool"} · {formatTime(r.tx.status.block_time)}</Row>
        <Row label="In / out">{formatBtc(r.tx.input_value)} → {formatBtc(r.tx.output_value)}</Row>
        <Row label="Fee">{formatBtc(r.tx.fee)} ({r.tx.feerate} sat/vB)</Row>
        {r.price_usd !== null && <Row label="BTC price then">${r.price_usd.toLocaleString()}</Row>}
        <Row label="Flags">{r.flags.length ? r.flags.map((f) => <span key={f} className="ml-1 mono text-xs">{f}</span>) : "—"}</Row>
      </div>
      <section>
        <h3 className="font-semibold text-sm mb-1">Findings</h3>
        <FindingList findings={r.findings} />
      </section>
      {fp && (
        <section>
          <h3 className="font-semibold text-sm mb-1">Wallet fingerprint</h3>
          {["version", "locktime_kind", "anti_fee_sniping", "rbf", "bip69", "low_r_only", "input_types", "output_types"].map((k) => (
            <Row key={k} label={k}>{JSON.stringify(fp[k])}</Row>
          ))}
        </section>
      )}
      <section>
        <h3 className="font-semibold text-sm mb-1">Inputs</h3>
        {r.tx.vin.map((i) => (
          <Row key={i.n} label={`#${i.n}`}>
            {i.is_coinbase ? "coinbase" : `${r.addresses[i.prevout?.address ?? ""]?.label ?? shortAddr(i.prevout?.address ?? "?")} · ${formatBtc(i.prevout?.value ?? 0)}`}
            {!i.is_coinbase && <button className="ml-2 underline text-xs" onClick={() => void openTx(i.prev_txid)}>open {shortTxid(i.prev_txid)}</button>}
          </Row>
        ))}
        <h3 className="font-semibold text-sm mb-1 mt-2">Outputs</h3>
        {r.tx.vout.map((o) => (
          <Row key={o.n} label={`#${o.n}`}>
            {o.address ? `${r.addresses[o.address]?.label ?? shortAddr(o.address)} · ${formatBtc(o.value)}` : `${o.script_type} · ${formatBtc(o.value)}`}
          </Row>
        ))}
      </section>
    </div>
  );
}

function TagEditor({ address }: { address: string }) {
  const categories = useCatalog<Category>("categories");
  const [label, setLabel] = useState("");
  const [category, setCategory] = useState("perpetrator");
  const [abuse, setAbuse] = useState("");
  const entities = (categories.data ?? []).filter((c) => c.kind === "entity");
  const abuses = (categories.data ?? []).filter((c) => c.kind === "abuse");
  return (
    <form
      className="space-y-1 text-sm"
      onSubmit={(e) => {
        e.preventDefault();
        if (!label.trim()) return;
        void addTag({ address, label: label.trim(), category, abuse: abuse || null });
        setLabel("");
      }}
    >
      <label className="block">Label <input className="input w-full" value={label} onChange={(e) => setLabel(e.target.value)} /></label>
      <label className="block">Category
        <select className="input w-full" value={category} onChange={(e) => setCategory(e.target.value)}>
          {entities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <label className="block">Abuse
        <select className="input w-full" value={abuse} onChange={(e) => setAbuse(e.target.value)}>
          <option value="">—</option>
          {abuses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <button className="btn btn-primary" type="submit">Add tag</button>
    </form>
  );
}

function TagList({ tags }: { tags: Tag[] }) {
  if (!tags.length) return <p className="muted text-sm">No attribution tags.</p>;
  return (
    <ul className="text-sm space-y-1">
      {tags.map((t) => (
        <li key={`${t.id}-${t.pack}-${t.label}`} className="border-b border-[var(--border)] pb-1">
          <strong>{t.label}</strong> <span className="muted">{t.category}{t.abuse ? ` / ${t.abuse}` : ""} · {t.confidence} ({t.confidence_level})</span>
          <div className="muted text-xs break-all"><span>{t.pack}</span> · <span>{t.source}</span></div>
        </li>
      ))}
    </ul>
  );
}

function AddressInspector({ address }: { address: string }) {
  const q = useQuery({ queryKey: ["address", address], queryFn: () => api.address(address) });
  const txs = useQuery({ queryKey: ["address-txs", address], queryFn: () => api.addressTxs(address) });
  const caseId = useWorkbench((s) => s.caseId);
  if (q.isLoading) return <p className="muted">Loading address…</p>;
  if (q.error || !q.data) return <p className="text-[var(--danger)]">{String(q.error ?? "not found")}</p>;
  const r: AddressResponse = q.data;
  return (
    <div className="space-y-3">
      <h2 className="font-semibold mono break-all">{address}</h2>
      <div className="flex flex-wrap gap-1">
        <button className="btn" onClick={() => void startTrace({ address }, { direction: "forward" })}>Trace forward</button>
        <button className="btn" onClick={() => void startTrace({ address }, { direction: "backward" })}>Trace backward</button>
        <button className="btn" onClick={() => void expandCluster(address)}>Expand cluster</button>
        <button className="btn" disabled={!caseId} title={caseId ? "" : "Save the case first"} onClick={() => void watchAddress(address)}>Watch in case</button>
      </div>
      <div>
        <Row label="Risk"><span style={{ color: `var(--risk-${r.info.risk})` }}>{r.info.risk}</span></Row>
        <Row label="Balance">{formatBtc(r.stats.balance)}</Row>
        <Row label="Received / sent">{formatBtc(r.stats.funded_sum)} / {formatBtc(r.stats.spent_sum)}</Row>
        <Row label="Transactions">{r.stats.tx_count}</Row>
        {r.cluster && (
          <Row label="Cluster">{shortAddr(r.cluster.root)} · {r.cluster.size} addresses{r.cluster.partial ? " (partial)" : ""}{r.cluster.capped ? " · large service?" : ""}</Row>
        )}
      </div>
      <section>
        <h3 className="font-semibold text-sm mb-1">Tags</h3>
        <TagList tags={r.info.tags} />
      </section>
      <section>
        <h3 className="font-semibold text-sm mb-1">Add tag</h3>
        <TagEditor address={address} />
      </section>
      <section>
        <h3 className="font-semibold text-sm mb-1">Recent transactions</h3>
        {(txs.data?.txs ?? []).map((t) => (
          <Row key={t.txid} label={formatTime(t.block_time)}>
            <span className="mono">{shortTxid(t.txid)}</span> {t.delta !== null && <span>{t.delta >= 0 ? "+" : ""}{formatBtc(t.delta)}</span>}
            <button className="ml-2 underline text-xs" onClick={() => void openTx(t.txid)}>add to graph</button>
          </Row>
        ))}
      </section>
    </div>
  );
}

export default function Inspector() {
  const selected = useWorkbench((s) => s.selected);
  const node = useWorkbench((s) => (s.selected ? s.graph.nodes[s.selected] : undefined));
  if (!selected) return <p className="muted text-sm p-3">Select a node to inspect it. Right-click nodes for actions.</p>;
  const [kind, ...rest] = selected.split(":");
  const value = rest.join(":");
  return (
    <div className="p-3 overflow-auto h-full">
      {kind === "tx" && <TxInspector txid={value} />}
      {kind === "addr" && <AddressInspector address={value} />}
      {kind === "script" && (
        <div className="space-y-1">
          <h2 className="font-semibold">{node?.label ?? "Script output"}</h2>
          <Row label="Value">{formatBtc(Number(node?.data.value ?? 0))}</Row>
        </div>
      )}
    </div>
  );
}
