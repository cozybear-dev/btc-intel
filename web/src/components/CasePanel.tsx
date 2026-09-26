import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { toSaved } from "../graph/model";
import { formatTime } from "../lib/format";
import { deleteCase, loadCase, newCase, saveCase } from "../state/actions";
import { useWorkbench } from "../state/store";
import { downloadText, edgesCsv, markdownReport } from "../export/export";

export default function CasePanel({ onExportPng }: { onExportPng: () => void }) {
  const queryClient = useQueryClient();
  const cases = useQuery({ queryKey: ["cases"], queryFn: api.cases });
  const s = useWorkbench();
  const current = useQuery({ queryKey: ["case", s.caseId], queryFn: () => api.getCase(s.caseId!), enabled: !!s.caseId });
  const slug = (s.caseName || "case").replace(/[^a-z0-9]+/gi, "-").toLowerCase();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["cases"] });
  return (
    <div className="p-3 space-y-3 overflow-auto h-full text-sm">
      <label className="block">Case name
        <input className="input w-full" value={s.caseName} onChange={(e) => s.setCaseName(e.target.value)} placeholder="e.g. Bitget hot wallet 2026-09-24" />
      </label>
      <label className="block">Notes
        <textarea className="input w-full h-32" value={s.notes} onChange={(e) => s.setNotes(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={async () => { await saveCase(); await refresh(); }}>{s.dirty ? "Save*" : "Save"}</button>
        <button className="btn" onClick={() => newCase()}>New</button>
        <label className="flex items-center gap-1"><input type="checkbox" checked={s.groupClusters} onChange={(e) => s.setGroupClusters(e.target.checked)} /> group clusters</label>
      </div>
      <section>
        <h3 className="font-semibold mb-1">Export</h3>
        <div className="flex flex-wrap gap-1">
          <button className="btn" onClick={onExportPng}>PNG</button>
          <button className="btn" onClick={() => downloadText(`${slug}.graph.json`, JSON.stringify(toSaved(s.graph), null, 1), "application/json")}>Graph JSON</button>
          <button className="btn" onClick={() => downloadText(`${slug}.flows.csv`, edgesCsv(s.graph), "text/csv")}>Flows CSV</button>
          <button className="btn" onClick={() => downloadText(`${slug}.report.md`, markdownReport(s.graph, { caseName: s.caseName, notes: s.notes, generatedAt: new Date() }), "text/markdown")}>Report (Markdown)</button>
          <button className="btn" onClick={async () => downloadText(`${slug}.tags.yaml`, await api.exportTags("user"), "application/yaml")}>My tags (TagPack)</button>
        </div>
      </section>
      {current.data && current.data.watch.length > 0 && (
        <section>
          <h3 className="font-semibold mb-1">Watchlist</h3>
          <ul className="mono text-xs">{current.data.watch.map((a) => <li key={a}>{a}</li>)}</ul>
        </section>
      )}
      <section>
        <h3 className="font-semibold mb-1">Saved cases</h3>
        <ul className="space-y-1">
          {(cases.data ?? []).map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-2">
              <button className="underline text-left" onClick={() => void loadCase(c.id)}>{c.name}</button>
              <span className="muted text-xs">{c.nodes} nodes · {formatTime(c.updated_at)}</span>
              <button className="btn" aria-label={`delete ${c.name}`} onClick={async () => { await deleteCase(c.id); await refresh(); }}>✕</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
