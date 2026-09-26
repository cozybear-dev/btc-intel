import { render, screen } from "@testing-library/react";
import { txResponse } from "../test/fixtures";
import { mergeTx } from "../graph/model";
import { useWorkbench } from "../state/store";
import StatusBar from "./StatusBar";

beforeEach(() => useWorkbench.getState().reset());

test("shows graph counts, errors and job state", () => {
  useWorkbench.getState().updateGraph((g) => mergeTx(g, txResponse));
  useWorkbench.getState().setError("all backends failed");
  useWorkbench.getState().setJob({ id: "j", kind: "trace", status: "running", nodes: 4, stops: 1, error: null, reason: null, calls: 12 });
  render(<StatusBar />);
  expect(screen.getByTestId("graph-stats")).toHaveTextContent("1 txs · 3 addresses · 4 edges · 0 stops");
  expect(screen.getByRole("alert")).toHaveTextContent("all backends failed");
  expect(screen.getByText(/trace running/i)).toBeInTheDocument();
});
