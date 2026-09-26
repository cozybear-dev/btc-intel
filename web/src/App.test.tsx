import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./components/GraphCanvas", () => ({ default: () => <div data-testid="graph-canvas" /> }));
vi.mock("./components/KbBrowser", () => ({ default: ({ path }: { path: string }) => <div>KB {path}</div> }));
vi.mock("./components/AnalysisView", () => ({ default: ({ address }: { address: string }) => <div>Analysis of {address}</div> }));
vi.mock("./api/client", async () => {
  const actual = await vi.importActual<typeof import("./api/client")>("./api/client");
  return { ...actual, api: { health: vi.fn().mockResolvedValue({ status: "ok", version: "0.1.0" }), kb: vi.fn().mockResolvedValue([]), cases: vi.fn().mockResolvedValue([]) } };
});

import App from "./App";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
}

beforeEach(() => { window.location.hash = ""; });

test("renders the workbench with graph view and tabs", async () => {
  renderApp();
  expect(screen.getByText(/btc-intel workbench/i)).toBeInTheDocument();
  expect(screen.getByTestId("graph-canvas")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Inspector" })).toHaveAttribute("aria-selected", "true");
  await userEvent.click(screen.getByRole("tab", { name: "Trace" }));
  expect(screen.getByRole("button", { name: /start trace/i })).toBeInTheDocument();
  expect(await screen.findByText(/API 0.1.0/)).toBeInTheDocument();
});

test("switches to the knowledge base view", async () => {
  renderApp();
  await userEvent.click(screen.getByRole("button", { name: /knowledge base/i }));
  expect(await screen.findByText("KB index.md")).toBeInTheDocument();
});

test("renders the analysis view for an analysis route", () => {
  window.location.hash = "#/analysis/bc1qx";
  renderApp();
  expect(screen.getByText("Analysis of bc1qx")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Analysis" })).toBeInTheDocument();
});
