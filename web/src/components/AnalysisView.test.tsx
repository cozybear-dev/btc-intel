import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../state/actions", () => ({
  startAnalysis: vi.fn().mockResolvedValue(true), cancelJob: vi.fn(), saveAnalysisAsCase: vi.fn(),
}));

import * as actions from "../state/actions";
import { type JobState, useWorkbench } from "../state/store";
import { ANALYSED, RANSOM, analysisSections } from "../test/fixtures";
import AnalysisView from "./AnalysisView";

beforeEach(() => {
  useWorkbench.getState().reset();
  vi.mocked(actions.startAnalysis).mockClear();
  window.location.hash = "";
  document.title = "btc-intel workbench";
});

const STARTED = 1_700_000_000_000;
const ALL_STAGES = ["profile", "cluster", "backward", "forward"];

function setJob(patch: Partial<JobState> = {}) {
  useWorkbench.getState().setJob({
    id: "a1", kind: "analysis", status: "done", nodes: 5, stops: 3, error: null, reason: null, calls: 42,
    started: STARTED, finished: STARTED + 372_000, stages: ALL_STAGES, ...patch,
  });
}

function showDone(address = ANALYSED) {
  useWorkbench.getState().setAnalysis({ address, depth: "quick", sections: analysisSections, markdown: "# r" });
  setJob();
}

function showRunningDeep() {
  const { profile, verdict } = analysisSections;
  useWorkbench.getState().setAnalysis({ address: ANALYSED, depth: "deep", sections: { profile, verdict: { ...verdict!, final: false } }, markdown: null });
  setJob({ status: "running", calls: 17, nodes: 1234, started: Date.now() - 134_000, finished: null, stages: ["profile", "cluster"] });
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
  expect(screen.getByRole("status", { name: "Analysis progress" })).toHaveTextContent("Quick analysis complete in 6m 12s · 42 API calls");
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

test("a preliminary verdict left by a cancelled analysis reads incomplete, not still running", () => {
  const sections = { ...analysisSections, verdict: { ...analysisSections.verdict!, final: false } };
  useWorkbench.getState().setAnalysis({ address: ANALYSED, depth: "quick", sections, markdown: null });
  setJob({ status: "cancelled" });
  render(<AnalysisView address={ANALYSED} />);
  expect(screen.getByText("incomplete: analysis stopped before finishing")).toBeInTheDocument();
  expect(screen.queryByText("preliminary: tracing still running")).not.toBeInTheDocument();
});

test("a running deep analysis shows elapsed time, live counts and which stages are done", () => {
  showRunningDeep();
  render(<AnalysisView address={ANALYSED} />);
  const progress = screen.getByRole("status", { name: "Analysis progress" });
  expect(progress).toHaveTextContent("Deep analysis running · 2m 14s · 1,234 addresses and transactions found · 17 API calls");
  expect(within(progress).getByLabelText("Profile: done")).toBeInTheDocument();
  expect(within(progress).getByLabelText("Cluster: done")).toBeInTheDocument();
  expect(within(progress).getByLabelText("Sources: running")).toBeInTheDocument();
  expect(within(progress).getByLabelText("Destinations: running")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Going deeper…" })).toBeDisabled();
  expect(document.title).toBe("Analysing… · btc-intel workbench");
});

test("the elapsed time keeps ticking while the analysis runs", () => {
  vi.useFakeTimers({ now: STARTED + 134_000 });
  try {
    showRunningDeep();
    setJob({ status: "running", started: STARTED, finished: null, stages: ["profile"] });
    render(<AnalysisView address={ANALYSED} />);
    expect(screen.getByRole("status", { name: "Analysis progress" })).toHaveTextContent("2m 14s");
    act(() => vi.advanceTimersByTime(3_000));
    expect(screen.getByRole("status", { name: "Analysis progress" })).toHaveTextContent("2m 17s");
  } finally {
    vi.useRealTimers();
  }
});

test("a finished analysis says so, including in the tab title, and leaves the title on unmount", () => {
  showDone();
  const { unmount } = render(<AnalysisView address={ANALYSED} />);
  const progress = screen.getByRole("status", { name: "Analysis progress" });
  expect(within(progress).getByLabelText("Destinations: done")).toBeInTheDocument();
  expect(document.title).toBe("✓ Analysis done · btc-intel workbench");
  unmount();
  expect(document.title).toBe("btc-intel workbench");
});

test("a finished analysis that stopped early says why", () => {
  showDone();
  setJob({ reason: "API call budget of 120 exhausted" });
  render(<AnalysisView address={ANALYSED} />);
  expect(screen.getByRole("status", { name: "Analysis progress" })).toHaveTextContent("Stopped early: API call budget of 120 exhausted");
});

test("a cancelled deep analysis says so, marks unfinished stages and can be rerun", async () => {
  showRunningDeep();
  setJob({ status: "cancelled", started: STARTED, finished: STARTED + 121_000, stages: ["profile", "cluster"] });
  render(<AnalysisView address={ANALYSED} />);
  const progress = screen.getByRole("status", { name: "Analysis progress" });
  expect(progress).toHaveTextContent("Deep analysis cancelled after 2m 1s; the results below are partial");
  expect(within(progress).getByLabelText("Sources: not reached")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Go deeper" }));
  expect(actions.startAnalysis).toHaveBeenCalledWith(ANALYSED, "deep");
});

test("an analysis cancelled before any stage finished does not promise partial results", () => {
  showRunningDeep();
  setJob({ status: "cancelled", started: STARTED, finished: STARTED + 15_000, stages: [] });
  render(<AnalysisView address={ANALYSED} />);
  expect(screen.getByRole("status", { name: "Analysis progress" }).querySelector("span.font-semibold")).toHaveTextContent(/^Deep analysis cancelled after 15s$/);
});

test("a failed analysis shows the error", () => {
  showRunningDeep();
  setJob({ status: "error", error: "all backends failed", started: STARTED, finished: STARTED + 12_000, stages: ["profile"] });
  render(<AnalysisView address={ANALYSED} />);
  expect(screen.getByRole("status", { name: "Analysis progress" })).toHaveTextContent("Deep analysis failed after 12s: all backends failed");
  expect(document.title).toBe("Analysis failed · btc-intel workbench");
});

test("before the job starts the page says it is starting", () => {
  useWorkbench.getState().setAnalysis({ address: ANALYSED, depth: "deep", sections: {}, markdown: null });
  render(<AnalysisView address={ANALYSED} />);
  expect(screen.getByRole("status", { name: "Analysis progress" })).toHaveTextContent("Starting deep analysis…");
  expect(screen.getByRole("button", { name: "Going deeper…" })).toBeDisabled();
});

test("an analysis that could not start shows why", () => {
  useWorkbench.getState().setAnalysis({ address: ANALYSED, depth: "quick", sections: {}, markdown: null });
  useWorkbench.getState().setError("address not found");
  render(<AnalysisView address={ANALYSED} />);
  expect(screen.getByRole("status", { name: "Analysis progress" })).toHaveTextContent("Quick analysis could not start: address not found");
});
