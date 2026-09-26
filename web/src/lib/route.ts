import { useSyncExternalStore } from "react";

export type Route = { view: "graph" } | { view: "kb"; path: string } | { view: "analysis"; address: string };

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  if (h === "kb" || h.startsWith("kb/")) {
    const path = h.slice(3);
    return { view: "kb", path: path ? decodeURIComponent(path) : "index.md" };
  }
  if (h.startsWith("analysis/") && h.length > "analysis/".length) {
    return { view: "analysis", address: decodeURIComponent(h.slice("analysis/".length)) };
  }
  return { view: "graph" };
}

export function routeToHash(route: Route): string {
  if (route.view === "kb") return `#/kb/${route.path}`;
  if (route.view === "analysis") return `#/analysis/${encodeURIComponent(route.address)}`;
  return "#/graph";
}

function subscribe(callback: () => void) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash, () => "");
  return parseHash(hash);
}

export function navigate(route: Route) {
  window.location.hash = routeToHash(route);
}
