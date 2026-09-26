import { useQuery } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import { marked } from "marked";
import type { MouseEvent } from "react";
import { api } from "../api/client";
import type { Heuristic, Incident, Technique } from "../api/types";
import { navigate } from "../lib/route";
import { openAddress, openTx } from "../state/actions";

export function renderMarkdown(md: string): string {
  const html = marked.parse(md, { async: false }) as string;
  return DOMPurify.sanitize(html, { FORBID_TAGS: ["style", "iframe", "form"], FORBID_ATTR: ["style"] });
}

export function resolveKbLink(current: string, href: string): string | null {
  if (!href || href.startsWith("#") || /^[a-z][a-z0-9+.-]*:/i.test(href)) return null;
  const parts = current.split("/").slice(0, -1);
  for (const segment of href.split("#")[0].split("/")) {
    if (segment === "..") parts.pop();
    else if (segment && segment !== ".") parts.push(segment);
  }
  return parts.join("/");
}

function useCollection<T>(name: "heuristics" | "techniques" | "incidents") {
  return useQuery({ queryKey: ["kb", name], queryFn: () => api.kb<T>(name), staleTime: Infinity });
}

function NavLink({ path, label }: { path: string; label: string }) {
  return (
    <li><a className="hover:underline" href={`#/kb/${path}`}>{label}</a></li>
  );
}

export default function KbBrowser({ path }: { path: string }) {
  const heuristics = useCollection<Heuristic>("heuristics");
  const techniques = useCollection<Technique>("techniques");
  const incidents = useCollection<Incident>("incidents");
  const page = useQuery({ queryKey: ["kb-page", path], queryFn: () => api.kbPage(path) });
  const incident = (incidents.data ?? []).find((i) => i.kb === path);

  const onClick = (e: MouseEvent<HTMLElement>) => {
    const anchor = (e.target as HTMLElement).closest("a");
    if (!anchor) return;
    const href = anchor.getAttribute("href") ?? "";
    const internal = resolveKbLink(path, href);
    if (internal && internal.endsWith(".md")) {
      e.preventDefault();
      navigate({ view: "kb", path: internal });
    } else if (/^https?:/i.test(href)) {
      e.preventDefault();
      window.open(href, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="flex h-full min-h-0">
      <nav className="w-72 shrink-0 overflow-auto border-r border-[var(--border)] p-3 text-sm space-y-3">
        <ul><NavLink path="index.md" label="Index" /><NavLink path="ttp-matrix.md" label="TTP matrix" /></ul>
        <div><h3 className="font-semibold">Analysis techniques</h3>
          <ul>{(heuristics.data ?? []).map((h) => <NavLink key={h.id} path={h.kb} label={`${h.parent ? "↳ " : ""}${h.id} ${h.name}`} />)}</ul></div>
        <div><h3 className="font-semibold">Obfuscation & laundering</h3>
          <ul>{(techniques.data ?? []).map((t) => <NavLink key={t.id} path={t.kb} label={`${t.id} ${t.name}`} />)}</ul></div>
        <div><h3 className="font-semibold">Incidents</h3>
          <ul>{[...(incidents.data ?? [])].sort((a, b) => a.date.localeCompare(b.date)).map((i) => <NavLink key={i.id} path={i.kb} label={`${i.date.slice(0, 4)} ${i.name}`} />)}</ul></div>
      </nav>
      <main className="flex-1 overflow-auto p-6">
        {incident && (
          <aside className="panel p-3 mb-4 text-sm">
            <h2 className="font-semibold mb-1">Seeds</h2>
            {incident.seeds.length === 0 && <p className="muted">{incident.seeds_note}</p>}
            <ul>
              {incident.seeds.map((s) => (
                <li key={s.value} className="flex items-center gap-2">
                  <span className="mono break-all">{s.value}</span>
                  <span className="muted">{s.role}{s.note ? ` · ${s.note}` : ""}</span>
                  <button
                    className="btn"
                    aria-label={`open ${s.value} in graph`}
                    onClick={() => {
                      navigate({ view: "graph" });
                      void (s.kind === "tx" ? openTx(s.value) : openAddress(s.value));
                    }}
                  >
                    Open in graph
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        )}
        {page.isLoading && <p className="muted">Loading…</p>}
        {page.error && <p className="text-[var(--danger)]">{String(page.error)}</p>}
        {page.data && (
          <article className="kb-article max-w-3xl" onClick={onClick} dangerouslySetInnerHTML={{ __html: renderMarkdown(page.data.markdown) }} />
        )}
      </main>
    </div>
  );
}
