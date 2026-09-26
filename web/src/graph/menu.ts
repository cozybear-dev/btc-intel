import type { NodeKind } from "../api/types";

export type MenuAction =
  | "expand-outputs" | "expand-inputs" | "trace-forward" | "trace-backward" | "follow-peel"
  | "expand-cluster" | "select" | "hide" | "remove";

const ITEMS: Record<NodeKind, { action: MenuAction; label: string }[]> = {
  tx: [
    { action: "expand-outputs", label: "Expand outputs (who received)" },
    { action: "expand-inputs", label: "Expand inputs (where from)" },
    { action: "trace-forward", label: "Trace forward from here" },
    { action: "trace-backward", label: "Trace backward from here" },
    { action: "follow-peel", label: "Follow peel chain" },
    { action: "hide", label: "Hide" },
    { action: "remove", label: "Remove from graph" },
  ],
  address: [
    { action: "trace-forward", label: "Trace forward (received funds)" },
    { action: "trace-backward", label: "Trace backward (source of funds)" },
    { action: "expand-cluster", label: "Expand cluster (common-input)" },
    { action: "select", label: "Inspect / tag" },
    { action: "hide", label: "Hide" },
    { action: "remove", label: "Remove from graph" },
  ],
  script: [
    { action: "hide", label: "Hide" },
    { action: "remove", label: "Remove from graph" },
  ],
};

export function menuItems(kind: NodeKind) {
  return ITEMS[kind];
}
