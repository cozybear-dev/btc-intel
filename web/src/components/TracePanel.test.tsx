import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../state/actions", () => ({ startTrace: vi.fn(), cancelJob: vi.fn() }));

import * as actions from "../state/actions";
import { useWorkbench } from "../state/store";
import TracePanel, { buildPolicy, seedFromNode } from "./TracePanel";

beforeEach(() => useWorkbench.getState().reset());

test("seedFromNode and buildPolicy", () => {
  expect(seedFromNode(`tx:${"ab".repeat(32)}`)).toEqual({ txid: "ab".repeat(32) });
  expect(seedFromNode("addr:bc1qx")).toEqual({ address: "bc1qx" });
  expect(seedFromNode("script:x:1")).toBeNull();
  expect(buildPolicy({ direction: "backward", taint_model: "fifo", max_hops: "4", min_value_btc: "0.001", max_txs: "50", max_calls: "200", coinjoin: "through", peel_mode: true }))
    .toEqual({ direction: "backward", taint_model: "fifo", max_hops: 4, min_value_sats: 100_000, max_txs: 50, max_calls: 200, coinjoin: "through", peel_mode: true });
});

test("starts a trace from the selected node", async () => {
  useWorkbench.getState().select(`tx:${"ab".repeat(32)}`);
  render(<TracePanel />);
  await userEvent.selectOptions(screen.getByLabelText(/direction/i), "backward");
  await userEvent.click(screen.getByRole("button", { name: /start trace/i }));
  expect(actions.startTrace).toHaveBeenCalledWith({ txid: "ab".repeat(32) }, expect.objectContaining({ direction: "backward", max_hops: 6 }));
});

test("start is disabled without a selection and stops are listed", async () => {
  useWorkbench.getState().updateGraph((g) => ({ ...g, stops: [{ node: "addr:bc1qx", reason: "labeled", taint: 5000, detail: "exchange: X" }] }));
  render(<TracePanel />);
  expect(screen.getByRole("button", { name: /start trace/i })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: /exchange: X/ }));
  expect(useWorkbench.getState().selected).toBe("addr:bc1qx");
});
