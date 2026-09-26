import { useEffect } from "react";
import type { Bucket, ClusterSummary, Exposure, Profile, RiskLevel, Verdict } from "../api/types";
import { addrNodeId } from "../graph/model";
import { formatBtc, formatPct, formatTime } from "../lib/format";
import { navigate } from "../lib/route";
import { cancelJob, saveAnalysisAsCase, startAnalysis } from "../state/actions";
import { useWorkbench } from "../state/store";

function openInGraph(nodeId: string | null) {
  navigate({ view: "graph" });
  useWorkbench.getState().select(nodeId);
}

function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className="px-2 py-0.5 rounded text-sm font-semibold uppercase text-white" style={{ background: `var(--risk-${level})` }}>
      {level}
    </span>
  );
}

function Pending({ what, active }: { what: string; active: boolean }) {
  return <p className={`muted text-sm ${active ? "animate-pulse" : ""}`}>{active ? `${what}…` : "Not available."}</p>;
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 text-sm py-0.5">
      <span className="muted whitespace-nowrap">{label}</span>
      <span className="text-right break-all">{children}</span>
    </div>
  );
}

function VerdictPanel({ verdict }: { verdict: Verdict }) {
  return (
    <section aria-label="Verdict" className="panel p-4 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <RiskBadge level={verdict.level} />
        {!verdict.final && <span className="muted text-sm">preliminary: tracing still running</span>}
        {verdict.low_confidence && <span className="text-sm" style={{ color: "var(--risk-medium)" }}>low confidence: try Go deeper</span>}
      </div>
      <h2 className="font-semibold">Why</h2>
      <ul className="list-disc pl-5 space-y-1 text-sm">
        {verdict.reasons.map((r, i) => (
          <li key={i}>
            <span className="font-semibold" style={{ color: `var(--risk-${r.level})` }}>{r.level}</span> {r.text}
          </li>
        ))}
      </ul>
      <p className="muted text-sm">{verdict.coverage}</p>
    </section>
  );
}

function ProfilePanel({ p }: { p: Profile }) {
  const fp = p.fingerprint;
  const behaviour = Object.entries(p.behaviour).map(([k, n]) => `${k} ×${n}`).join(", ");
  const tags = p.info.tags.slice(0, 5).map((t) => `${t.label} (${t.abuse ?? t.category})`).join(", ");
  return (
    <section aria-label="Profile" className="panel p-4">
      <h2 className="font-semibold mb-1">Profile</h2>
      <Fact label="Balance">{formatBtc(p.stats.balance)}</Fact>
      <Fact label="Received / sent">{formatBtc(p.stats.funded_sum)} / {formatBtc(p.stats.spent_sum)}</Fact>
      <Fact label="Transactions">{p.stats.tx_count} ({p.txs_seen} analysed)</Fact>
      <Fact label="Active">
        {p.first_seen === null ? "no confirmed activity" : `${formatTime(p.first_seen)}${p.history_complete ? "" : " or earlier"} → ${formatTime(p.last_seen)}`}
      </Fact>
      <Fact label="Longest quiet period">{p.longest_gap_days === null ? "—" : `${p.longest_gap_days} days`}</Fact>
      <Fact label="Address type">{p.address_type ?? "unknown"}{p.reused ? " · reused" : ""}</Fact>
      <Fact label="Labels">{tags || "none"}</Fact>
      <Fact label="Behaviour">{behaviour || "nothing notable"}</Fact>
      <Fact label="Wallet fingerprint">
        {fp.signed_txs ? `${fp.signature} in ${formatPct(fp.share)} of ${fp.signed_txs} signed txs` : "no signed transactions"}
      </Fact>
    </section>
  );
}

function ClusterPanel({ c }: { c: ClusterSummary }) {
  return (
    <section aria-label="Cluster" className="panel p-4">
      <h2 className="font-semibold mb-1">Cluster (co-spent addresses)</h2>
      <Fact label="Size">{c.size} addresses{c.partial ? " (partial)" : ""}{c.capped ? " · capped: large service?" : ""}</Fact>
      <Fact label="Labels">{c.top_labels.length ? c.top_labels.map((t) => `${t.label} ×${t.count}`).join(", ") : "none"}</Fact>
      {c.conflicts.length > 0 && <Fact label="Conflicting labels">{c.conflicts.map((x) => x.labels.join(" / ")).join("; ")}</Fact>}
      {c.error && <p className="text-sm text-[var(--danger)]">Expansion failed: {c.error}</p>}
    </section>
  );
}

function BucketRow({ b }: { b: Bucket }) {
  const category = b.kind === "labeled" ? b.key : b.kind === "own_cluster" ? `${b.key} (own cluster)` : b.kind.replace("_", " ");
  return (
    <tr className="border-t border-[var(--border)]">
      <td className="py-1">
        <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: `var(--risk-${b.risk})` }} />
        {b.nodes.length ? <button className="underline" onClick={() => openInGraph(b.nodes[0])}>{b.label}</button> : b.label}
      </td>
      <td>{category}</td>
      <td className="text-right mono">{formatBtc(b.amount)}</td>
      <td className="text-right">{formatPct(b.share)}</td>
      <td className="text-right">{b.min_hops ?? "—"}</td>
      <td className="pl-3 muted">{b.source ?? "—"}</td>
    </tr>
  );
}

function ExposureTable({ title, e }: { title: string; e: Exposure }) {
  return (
    <section aria-label={title} className="panel p-4">
      <h2 className="font-semibold mb-1">{title}</h2>
      {e.error && <p className="text-sm text-[var(--danger)]">Trace failed: {e.error}</p>}
      {e.buckets.length === 0 ? (
        <p className="muted text-sm">No funds to trace.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="muted text-left">
            <tr>
              <th className="py-1">Where</th><th>Category</th><th className="text-right">Amount</th>
              <th className="text-right">Share</th><th className="text-right">Hops</th><th className="pl-3">Source</th>
            </tr>
          </thead>
          <tbody>{e.buckets.map((b) => <BucketRow key={`${b.kind}-${b.key}-${b.label}`} b={b} />)}</tbody>
        </table>
      )}
      {e.incomplete && e.reason && !e.error && <p className="muted text-xs mt-1">Stopped early: {e.reason}</p>}
    </section>
  );
}

export default function AnalysisView({ address }: { address: string }) {
  const analysis = useWorkbench((s) => s.analysis);
  const job = useWorkbench((s) => s.job);
  const error = useWorkbench((s) => s.error);

  useEffect(() => {
    // startAnalysis sets `analysis` synchronously, so StrictMode's second effect run is a no-op
    if (useWorkbench.getState().analysis?.address === address) return;
    void startAnalysis(address).then((started) => {
      if (!started) navigate({ view: "graph" });
    });
  }, [address]);

  if (!analysis || analysis.address !== address) {
    return <div className="p-4"><Pending what="Starting analysis" active /></div>;
  }
  const { sections } = analysis;
  const running = job?.kind === "analysis" && job.status === "running";
  const pending = running || (!job && !error);
  const status = running ? `analysing… ${job?.calls ?? 0} API calls`
    : job?.status === "done" ? `done · ${job.calls ?? 0} API calls`
    : job?.status === "error" ? `failed: ${job.error}`
    : job?.status ?? (error ? `failed: ${error}` : "");
  const seed = addrNodeId(sections.profile?.address ?? address);
  return (
    <div className="h-full overflow-auto">
      <div className="max-w-5xl mx-auto p-4 space-y-4">
        <header className="flex flex-wrap items-center gap-3">
          <h1 className="mono text-lg break-all">{address}</h1>
          <button className="btn" onClick={() => void navigator.clipboard?.writeText(address)}>Copy</button>
          <span className="muted text-sm">{analysis.depth} analysis{status ? ` · ${status}` : ""}</span>
          <div className="ml-auto flex flex-wrap gap-2">
            {running && <button className="btn" onClick={() => void cancelJob()}>Cancel</button>}
            <button className="btn btn-primary" onClick={() => openInGraph(seed)}>Open in graph</button>
            <button className="btn" disabled={running || analysis.depth === "deep"} onClick={() => void startAnalysis(address, "deep")}>Go deeper</button>
            <button className="btn" disabled={!analysis.markdown} onClick={() => void saveAnalysisAsCase()}>Save as case</button>
          </div>
        </header>
        {sections.verdict ? <VerdictPanel verdict={sections.verdict} /> : <Pending what="Checking labels" active={pending} />}
        <div className="grid gap-4 md:grid-cols-2">
          {sections.profile ? <ProfilePanel p={sections.profile} /> : <Pending what="Loading profile" active={pending} />}
          {sections.cluster ? <ClusterPanel c={sections.cluster} /> : <Pending what="Expanding cluster" active={pending} />}
        </div>
        {sections.sources ? <ExposureTable title="Sources of funds" e={sections.sources} /> : <Pending what="Tracing where the funds came from" active={pending} />}
        {sections.destinations ? <ExposureTable title="Destinations of funds" e={sections.destinations} /> : <Pending what="Tracing where the funds went" active={pending} />}
      </div>
    </div>
  );
}
