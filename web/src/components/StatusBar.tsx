import { stats } from "../graph/model";
import { useWorkbench } from "../state/store";

export default function StatusBar() {
  const graph = useWorkbench((s) => s.graph);
  const busy = useWorkbench((s) => s.busy);
  const error = useWorkbench((s) => s.error);
  const message = useWorkbench((s) => s.message);
  const job = useWorkbench((s) => s.job);
  const n = stats(graph);
  return (
    <footer className="flex items-center gap-4 px-3 py-1 text-xs border-t border-[var(--border)] bg-[var(--panel)]">
      <span data-testid="graph-stats">{`${n.txs} txs · ${n.addresses} addresses · ${n.edges} edges · ${n.stops} stops`}</span>
      {busy > 0 && <span className="muted">loading… (public APIs are rate-limited)</span>}
      {job && (
        <span className="muted">
          {job.kind} {job.status}
          {job.calls !== null ? ` · ${job.calls} API calls` : ""}
          {job.reason ? ` · ${job.reason}` : ""}
        </span>
      )}
      {message && <span>{message}</span>}
      {error && <span role="alert" className="text-[var(--danger)]">{error}</span>}
    </footer>
  );
}
