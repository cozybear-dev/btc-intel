import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../state/actions", () => ({
  startAnalysis: vi.fn().mockResolvedValue(true), cancelJob: vi.fn(), saveAnalysisAsCase: vi.fn(),
}));

import * as actions from "../state/actions";
import { useWorkbench } from "../state/store";
import { ANALYSED, RANSOM, analysisSections } from "../test/fixtures";
import AnalysisView from "./AnalysisView";

beforeEach(() => {
  useWorkbench.getState().reset();
  vi.mocked(actions.startAnalysis).mockClear();
  window.location.hash = "";
});

function showDone(address = ANALYSED) {
  useWorkbench.getState().setAnalysis({ address, depth: "quick", sections: analysisSections, markdown: "# r" });
  useWorkbench.getState().setJob({ id: "a1", kind: "analysis", status: "done", nodes: 5, stops: 3, error: null, reason: null, calls: 42 });
}

test("starts an analysis for a new address and shows a placeholder", () => {
  render(<AnalysisView address="bc1qnew" />);
  expect(actions.startAnalysis).toHaveBeenCalledWith("bc1qnew");
  expect(screen.getByText(/Starting analysis/)).toBeInTheDocument();
});

test("renders verdict, reasons, profile and exposure tables; rows open the graph", async () => {
  showDone();
  render(<AnalysisView address={ANALYSED} />);
  expect(actions.startAnalysis).not.toHaveBeenCalled();
  const verdict = screen.getByRole("region", { name: "Verdict" });
  expect(within(verdict).getByText(/directly from LockBit/)).toBeInTheDocument();
  expect(within(verdict).getByText(/Traced 100% of funds/)).toBeInTheDocument();
  expect(screen.getByText(/done · 42 API calls/)).toBeInTheDocument();
  const sources = screen.getByRole("region", { name: "Sources of funds" });
  expect(within(sources).getByText("0.015 BTC")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Destinations of funds" })).getByText("67%")).toBeInTheDocument();
  await userEvent.click(within(sources).getByRole("button", { name: "LockBit" }));
  expect(window.location.hash).toBe("#/graph");
  expect(useWorkbench.getState().selected).toBe(`addr:${RANSOM}`);
});

test("buttons: go deeper and save as case", async () => {
  showDone();
  render(<AnalysisView address={ANALYSED} />);
  await userEvent.click(screen.getByRole("button", { name: "Save as case" }));
  expect(actions.saveAnalysisAsCase).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Go deeper" }));
  expect(actions.startAnalysis).toHaveBeenCalledWith(ANALYSED, "deep");
});

test("Open in graph uses the normalised address from the profile", async () => {
  showDone(ANALYSED.toUpperCase());
  render(<AnalysisView address={ANALYSED.toUpperCase()} />);
  await userEvent.click(screen.getByRole("button", { name: "Open in graph" }));
  expect(useWorkbench.getState().selected).toBe(`addr:${ANALYSED}`);
});
