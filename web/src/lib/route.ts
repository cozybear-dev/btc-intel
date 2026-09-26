import { useSyncExternalStore } from "react";

export type Route = { view: "graph" } | { view: "kb"; path: string };

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#\/?/, "");
  if (h === "kb" || h.startsWith("kb/")) {
    const path = h.slice(3);
    return { view: "kb", path: path ? decodeURIComponent(path) : "index.md" };
  }
  return { view: "graph" };
}

export function routeToHash(route: Route): string {
  return route.view === "kb" ? `#/kb/${route.path}` : "#/graph";
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
