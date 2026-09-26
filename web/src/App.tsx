import { useQuery } from "@tanstack/react-query";
import type { Core } from "cytoscape";
import { useCallback, useRef, useState } from "react";
import { api } from "./api/client";
import AnalysisView from "./components/AnalysisView";
import CasePanel from "./components/CasePanel";
import GraphCanvas from "./components/GraphCanvas";
import Inspector from "./components/Inspector";
import KbBrowser from "./components/KbBrowser";
import SearchBar from "./components/SearchBar";
import StatusBar from "./components/StatusBar";
import TracePanel from "./components/TracePanel";
import { exportPng as renderPng } from "./export/export";
import { navigate, useRoute } from "./lib/route";
import { useWorkbench } from "./state/store";

type Tab = "Inspector" | "Trace" | "Case";

export default function App() {
  const route = useRoute();
  const [tab, setTab] = useState<Tab>("Inspector");
  const cyRef = useRef<Core | null>(null);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const caseName = useWorkbench((s) => s.caseName);
  const lastAnalysis = useWorkbench((s) => s.analysis?.address ?? null);
  const onReady = useCallback((cy: Core) => { cyRef.current = cy; }, []);

  const exportPng = () => {
    const cy = cyRef.current;
    if (!cy) return;
    const bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() || "#ffffff";
    const filename = `${(caseName || "graph").replace(/[^a-z0-9]+/gi, "-").toLowerCase()}.png`;
    if (!renderPng(cy, filename, bg)) {
      useWorkbench.getState().setError("The graph is too large to render as PNG; hide nodes or export Graph JSON instead.");
    }
  };

  return (
    <div className="h-full flex flex-col">
      <header className="flex items-center gap-3 px-4 py-2 border-b border-[var(--border)] bg-[var(--panel)]">
        <span className="font-semibold whitespace-nowrap">btc-intel workbench</span>
        <SearchBar />
        <nav className="flex gap-1">
          <button className={`btn ${route.view === "graph" ? "btn-primary" : ""}`} onClick={() => navigate({ view: "graph" })}>Graph</button>
          <button
            className={`btn ${route.view === "analysis" ? "btn-primary" : ""}`}
            disabled={!lastAnalysis && route.view !== "analysis"}
            title={lastAnalysis ? "" : "Search an address to analyse it"}
            onClick={() => lastAnalysis && navigate({ view: "analysis", address: lastAnalysis })}
          >
            Analysis
          </button>
          <button className={`btn ${route.view === "kb" ? "btn-primary" : ""}`} onClick={() => navigate({ view: "kb", path: "index.md" })}>Knowledge base</button>
        </nav>
        <span className="muted text-xs whitespace-nowrap">
          {health.data ? `API ${health.data.version}` : health.error ? "API offline" : "…"}
        </span>
      </header>
      <div className="flex-1 min-h-0">
        {route.view === "kb" ? (
          <KbBrowser path={route.path} />
        ) : route.view === "analysis" ? (
          <AnalysisView address={route.address} />
        ) : (
          <div className="flex h-full">
            <div className="flex-1 min-w-0">
              <GraphCanvas onReady={onReady} />
            </div>
            <aside className="w-[420px] shrink-0 border-l border-[var(--border)] bg-[var(--panel)] flex flex-col min-h-0">
              <div role="tablist" className="flex border-b border-[var(--border)]">
                {(["Inspector", "Trace", "Case"] as Tab[]).map((t) => (
                  <button
                    key={t}
                    role="tab"
                    aria-selected={tab === t}
                    className={`flex-1 py-2 text-sm ${tab === t ? "font-semibold border-b-2 border-[var(--accent)]" : "muted"}`}
                    onClick={() => setTab(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="flex-1 min-h-0">
                {tab === "Inspector" && <Inspector />}
                {tab === "Trace" && <TracePanel />}
                {tab === "Case" && <CasePanel onExportPng={exportPng} />}
              </div>
            </aside>
          </div>
        )}
      </div>
      <StatusBar />
    </div>
  );
}
