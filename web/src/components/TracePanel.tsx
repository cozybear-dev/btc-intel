import { useState } from "react";
import type { StopReason, TracePolicy, TraceSeed } from "../api/types";
import { btcToSats, formatBtc, shortAddr } from "../lib/format";
import { cancelJob, startTrace } from "../state/actions";
import { useWorkbench } from "../state/store";

export interface PolicyForm {
  direction: "forward" | "backward";
  taint_model: "haircut" | "fifo" | "poison";
  max_hops: string;
  min_value_btc: string;
  max_txs: string;
  max_calls: string;
  coinjoin: "stop" | "through";
  peel_mode: boolean;
}

const DEFAULT_FORM: PolicyForm = {
  direction: "forward", taint_model: "haircut", max_hops: "6", min_value_btc: "0.0001", max_txs: "200",
  max_calls: "600", coinjoin: "stop", peel_mode: false,
};

export function buildPolicy(f: PolicyForm): Partial<TracePolicy> {
  return {
    direction: f.direction, taint_model: f.taint_model, max_hops: Number(f.max_hops),
    min_value_sats: btcToSats(f.min_value_btc) ?? 10_000, max_txs: Number(f.max_txs),
    max_calls: Number(f.max_calls), coinjoin: f.coinjoin, peel_mode: f.peel_mode,
  };
}

export function seedFromNode(id: string | null): TraceSeed | null {
  if (!id) return null;
  const [kind, ...rest] = id.split(":");
  const value = rest.join(":");
  if (kind === "tx") return { txid: value };
  if (kind === "addr") return { address: value };
  return null;
}

const REASONS: StopReason[] = ["labeled", "coinjoin", "unspent", "peel_off", "coinbase", "max_hops", "min_value", "max_txs"];

export default function TracePanel() {
  const [form, setForm] = useState<PolicyForm>(DEFAULT_FORM);
  const selected = useWorkbench((s) => s.selected);
  const job = useWorkbench((s) => s.job);
  const stops = useWorkbench((s) => s.graph.stops);
  const nodes = useWorkbench((s) => s.graph.nodes);
  const select = useWorkbench((s) => s.select);
  const seed = seedFromNode(selected);
  const set = <K extends keyof PolicyForm>(k: K, v: PolicyForm[K]) => setForm((f) => ({ ...f, [k]: v }));
  const field = "block text-sm";
  return (
    <div className="p-3 space-y-3 overflow-auto h-full">
      <p className="text-sm">Seed: {seed ? <span className="mono">{seed.txid ? `tx ${seed.txid.slice(0, 12)}…` : shortAddr(seed.address!)}</span> : <span className="muted">select a transaction or address</span>}</p>
      <div className="grid grid-cols-2 gap-2">
        <label className={field}>Direction
          <select className="input w-full" value={form.direction} onChange={(e) => set("direction", e.target.value as PolicyForm["direction"])}>
            <option value="forward">forward (where did it go?)</option>
            <option value="backward">backward (where from?)</option>
          </select>
        </label>
        <label className={field}>Taint model
          <select className="input w-full" value={form.taint_model} onChange={(e) => set("taint_model", e.target.value as PolicyForm["taint_model"])}>
            <option value="haircut">haircut</option>
            <option value="fifo">FIFO</option>
            <option value="poison">poison</option>
          </select>
        </label>
        <label className={field}>Max hops <input className="input w-full" value={form.max_hops} onChange={(e) => set("max_hops", e.target.value)} /></label>
        <label className={field}>Min value (BTC) <input className="input w-full" value={form.min_value_btc} onChange={(e) => set("min_value_btc", e.target.value)} /></label>
        <label className={field}>Max transactions <input className="input w-full" value={form.max_txs} onChange={(e) => set("max_txs", e.target.value)} /></label>
        <label className={field}>Max API calls <input className="input w-full" value={form.max_calls} onChange={(e) => set("max_calls", e.target.value)} /></label>
        <label className={field}>CoinJoins
          <select className="input w-full" value={form.coinjoin} onChange={(e) => set("coinjoin", e.target.value as PolicyForm["coinjoin"])}>
            <option value="stop">stop at CoinJoin</option>
            <option value="through">continue (probabilistic)</option>
          </select>
        </label>
        <label className="text-sm flex items-center gap-2 mt-5">
          <input type="checkbox" checked={form.peel_mode} onChange={(e) => set("peel_mode", e.target.checked)} /> Peel mode
        </label>
      </div>
      <div className="flex gap-2">
        <button className="btn btn-primary" disabled={!seed} onClick={() => seed && void startTrace(seed, buildPolicy(form))}>Start trace</button>
        <button className="btn" disabled={job?.status !== "running"} onClick={() => void cancelJob()}>Cancel</button>
      </div>
      {job && <p className="text-sm muted">{job.kind} {job.status} · {job.nodes} nodes · {job.stops} stops{job.error ? ` · ${job.error}` : ""}</p>}
      <section>
        <h3 className="font-semibold text-sm mb-1">Stops</h3>
        {REASONS.filter((r) => stops.some((s) => s.reason === r)).map((reason) => (
          <details key={reason} open={reason === "labeled"}>
            <summary className="text-sm cursor-pointer">{reason} ({stops.filter((s) => s.reason === reason).length})</summary>
            <ul className="text-sm">
              {stops.filter((s) => s.reason === reason).sort((a, b) => b.taint - a.taint).slice(0, 200).map((s, i) => (
                <li key={`${s.node}-${i}`}>
                  <button className="underline text-left" onClick={() => select(s.node)}>
                    {s.detail || nodes[s.node]?.label || s.node}
                  </button>{" "}
                  <span className="muted">{formatBtc(s.taint)}</span>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </section>
    </div>
  );
}
