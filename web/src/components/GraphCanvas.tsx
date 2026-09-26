import cytoscape, { type Core, type StylesheetStyle } from "cytoscape";
import dagre from "cytoscape-dagre";
import { useEffect, useMemo, useRef, useState } from "react";
import type { NodeKind } from "../api/types";
import { type MenuAction, menuItems } from "../graph/menu";
import { hideNodes, removeNode, setPositions } from "../graph/model";
import { buildStylesheet, currentPalette, toElements } from "../graph/style";
import { expandCluster, expandInputs, expandOutputs, followPeel, startTrace } from "../state/actions";
import { useWorkbench } from "../state/store";

cytoscape.use(dagre);

interface Menu { x: number; y: number; id: string; kind: NodeKind }

export async function runMenuAction(action: MenuAction, id: string) {
  const store = useWorkbench.getState();
  const [prefix, ...rest] = id.split(":");
  const value = rest.join(":");
  switch (action) {
    case "expand-outputs": return expandOutputs(value);
    case "expand-inputs": return expandInputs(value);
    case "follow-peel": return followPeel(value);
    case "trace-forward":
    case "trace-backward": {
      const direction = action === "trace-forward" ? "forward" : "backward";
      const seed = prefix === "tx" ? { txid: value } : { address: value };
      return startTrace(seed, { direction });
    }
    case "expand-cluster": return expandCluster(value);
    case "select": return store.select(id);
    case "hide": return store.updateGraph((g) => hideNodes(g, [id]));
    case "remove": return store.updateGraph((g) => removeNode(g, id));
  }
}

export default function GraphCanvas({ onReady }: { onReady?: (cy: Core) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [menu, setMenu] = useState<Menu | null>(null);
  const graph = useWorkbench((s) => s.graph);
  const groupClusters = useWorkbench((s) => s.groupClusters);
  const selected = useWorkbench((s) => s.selected);
  const palette = useMemo(() => currentPalette(), []);
  const elements = useMemo(() => toElements(graph, palette, { groupClusters }), [graph, palette, groupClusters]);

  useEffect(() => {
    const cy = cytoscape({
      container: container.current,
      style: buildStylesheet(palette) as unknown as StylesheetStyle[],
      wheelSensitivity: 0.3,
      minZoom: 0.05,
      maxZoom: 4,
    });
    cy.on("tap", "node", (e) => {
      setMenu(null);
      const kind = e.target.data("kind");
      if (kind !== "cluster") useWorkbench.getState().select(e.target.id());
    });
    cy.on("tap", (e) => {
      if (e.target === cy) {
        setMenu(null);
        useWorkbench.getState().select(null);
      }
    });
    cy.on("cxttap", "node", (e) => {
      const kind = e.target.data("kind");
      if (kind === "cluster") return;
      setMenu({ x: e.renderedPosition.x, y: e.renderedPosition.y, id: e.target.id(), kind });
    });
    cy.on("dragfree", "node", (e) => {
      const pos = e.target.position();
      useWorkbench.getState().updateGraph((g) => setPositions(g, { [e.target.id()]: { x: pos.x, y: pos.y } }));
    });
    cyRef.current = cy;
    onReady?.(cy);
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [palette, onReady]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    let added = 0;
    cy.batch(() => {
      const wanted = new Set(elements.map((e) => e.data.id as string));
      cy.elements().forEach((el) => {
        if (!wanted.has(el.id())) el.remove();
      });
      for (const el of elements) {
        const existing = cy.getElementById(el.data.id as string);
        if (existing.nonempty()) {
          existing.data(el.data);
          if (el.group === "nodes" && existing.isNode() && (existing.data("parent") ?? null) !== (el.data.parent ?? null)) {
            (existing as unknown as cytoscape.NodeSingular).move({ parent: (el.data.parent as string | undefined) ?? null });
          }
        } else {
          cy.add(el);
          added += 1;
        }
      }
    });
    const unpositioned = cy.nodes().filter((n) => !graph.positions[n.id()] && n.data("kind") !== "cluster");
    if (added > 0 && unpositioned.nonempty()) {
      cy.layout({ name: "dagre", rankDir: "LR", nodeSep: 18, rankSep: 70, fit: true, animate: false } as cytoscape.LayoutOptions).run();
    }
  }, [elements, graph.positions]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.$(":selected").unselect();
    if (selected) cy.getElementById(selected).select();
  }, [selected]);

  return (
    <div className="relative h-full w-full" onContextMenu={(e) => e.preventDefault()}>
      <div ref={container} className="h-full w-full" data-testid="graph-canvas" />
      {Object.keys(graph.nodes).length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center muted pointer-events-none text-sm">
          Search a txid, txid:vout, address or tag to start an investigation.
        </div>
      )}
      {menu && (
        <ul className="absolute panel shadow-lg py-1 text-sm z-10 min-w-56" style={{ left: menu.x, top: menu.y }} role="menu">
          {menuItems(menu.kind).map((item) => (
            <li key={item.action}>
              <button
                role="menuitem"
                className="w-full text-left px-3 py-1 hover:bg-[var(--panel-2)]"
                onClick={() => {
                  setMenu(null);
                  void runMenuAction(item.action, menu.id);
                }}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
