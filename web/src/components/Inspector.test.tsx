import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { txResponse } from "../test/fixtures";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    api: {
      tx: vi.fn(),
      address: vi.fn(),
      addressTxs: vi.fn(),
      cluster: vi.fn(),
      kb: vi.fn(),
      addTag: vi.fn(),
    },
  };
});
vi.mock("../state/actions", () => ({
  expandOutputs: vi.fn(), expandInputs: vi.fn(), followPeel: vi.fn(), startTrace: vi.fn(),
  expandCluster: vi.fn(), openTx: vi.fn(), addTag: vi.fn(), watchAddress: vi.fn(),
}));

import { api } from "../api/client";
import * as actions from "../state/actions";
import { useWorkbench } from "../state/store";
import Inspector, { findingKbLink } from "./Inspector";

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;
const TXID = "aa".repeat(32);

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  useWorkbench.getState().reset();
  mocked.kb.mockResolvedValue([
    { id: "H-CHG", name: "Change", kb: "heuristics/h-chg.md" },
    { id: "exchange", name: "Exchange", risk: "low", kind: "entity" },
    { id: "perpetrator", name: "Perpetrator", risk: "high", kind: "entity" },
    { id: "theft", name: "Theft", risk: "severe", kind: "abuse" },
  ]);
});

test("findingKbLink resolves heuristic pages", () => {
  const hs = [{ id: "H-CHG", kb: "heuristics/h-chg.md" }] as never;
  expect(findingKbLink("H-CHG", hs)).toBe("#/kb/heuristics/h-chg.md");
  expect(findingKbLink("H-NOPE", hs)).toBeNull();
});

test("transaction inspector shows findings with KB links and runs actions", async () => {
  mocked.tx.mockResolvedValue({
    ...txResponse,
    findings: [{ heuristic: "H-CHG", subject: `out:${TXID}:1`, label: "change", confidence: 0.77, evidence: {} }],
  });
  useWorkbench.getState().select(`tx:${TXID}`);
  wrap(<Inspector />);
  expect(await screen.findByText("change")).toBeInTheDocument();
  // the heuristics catalogue loads after the transaction, so the KB link appears asynchronously
  expect(await screen.findByRole("link", { name: "H-CHG" })).toHaveAttribute("href", "#/kb/heuristics/h-chg.md");
  await userEvent.click(screen.getByRole("button", { name: /expand outputs/i }));
  expect(actions.expandOutputs).toHaveBeenCalledWith(TXID);
  expect(screen.getByText("peel_step")).toBeInTheDocument();
});

test("address inspector shows tags and submits the tag form", async () => {
  mocked.address.mockResolvedValue({
    stats: { address: "bc1qdst", tx_count: 2, funded_txo_count: 1, funded_sum: 60_000, spent_txo_count: 0, spent_sum: 0, mempool_tx_count: 0, mempool_delta: 0, balance: 60_000 },
    info: { address: "bc1qdst", tags: [{ id: 1, address: "bc1qdst", label: "Exchange", category: "exchange", abuse: null, actor: null, confidence: "authority_data", confidence_level: 60, source: "https://example.org", pack: "gs:x", is_cluster_definer: false, lastmod: null, created_by: "import" }], cluster: null, category: "exchange", label: "Exchange", risk: "low", stop_category: "exchange" },
    cluster: null,
  });
  mocked.addressTxs.mockResolvedValue({ txs: [], next: null });
  useWorkbench.getState().select("addr:bc1qdst");
  wrap(<Inspector />);
  expect(await screen.findByText("gs:x")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/label/i), "Suspect wallet");
  await userEvent.selectOptions(screen.getByLabelText(/category/i), "perpetrator");
  await userEvent.selectOptions(screen.getByLabelText(/abuse/i), "theft");
  await userEvent.click(screen.getByRole("button", { name: /add tag/i }));
  expect(actions.addTag).toHaveBeenCalledWith(expect.objectContaining({ address: "bc1qdst", label: "Suspect wallet", category: "perpetrator", abuse: "theft" }));
});

test("tag labels are rendered as text, not HTML", async () => {
  mocked.address.mockResolvedValue({
    stats: { address: "bc1qx", tx_count: 0, funded_txo_count: 0, funded_sum: 0, spent_txo_count: 0, spent_sum: 0, mempool_tx_count: 0, mempool_delta: 0, balance: 0 },
    info: { address: "bc1qx", tags: [{ id: 2, address: "bc1qx", label: "<img src=x onerror=alert(1)>", category: "unknown", abuse: null, actor: null, confidence: "unknown", confidence_level: 5, source: "s", pack: "p", is_cluster_definer: false, lastmod: null, created_by: "import" }], cluster: null, category: null, label: null, risk: "none", stop_category: null },
    cluster: null,
  });
  mocked.addressTxs.mockResolvedValue({ txs: [], next: null });
  useWorkbench.getState().select("addr:bc1qx");
  const { container } = wrap(<Inspector />);
  expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
  expect(container.querySelector("img")).toBeNull();
});
