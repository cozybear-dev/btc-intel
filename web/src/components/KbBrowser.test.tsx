import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return { ...actual, api: { kb: vi.fn(), kbPage: vi.fn() } };
});
vi.mock("../state/actions", () => ({ openTx: vi.fn(), openAddress: vi.fn() }));

import { api } from "../api/client";
import * as actions from "../state/actions";
import KbBrowser, { renderMarkdown, resolveKbLink } from "./KbBrowser";

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

test("renderMarkdown strips scripts and event handlers", () => {
  // the links need their own paragraph: on the <script> line marked keeps them as inert raw-HTML text
  const html = renderMarkdown("# T\n\n<script>alert(1)</script><img src=x onerror=alert(1)>\n\n[x](javascript:alert(1)) [y](JaVaScRiPt:alert(2))");
  expect(html).toContain("<h1");
  expect(html).not.toContain("<script");
  expect(html).not.toContain("onerror");
  expect(html.toLowerCase()).not.toContain("javascript:");
  expect(html).toContain("<a>x</a>");
});

test("resolveKbLink handles relative paths and ignores external links", () => {
  expect(resolveKbLink("heuristics/h-cioh.md", "h-chg.md")).toBe("heuristics/h-chg.md");
  expect(resolveKbLink("heuristics/h-cioh.md", "../incidents/i-2016-bitfinex.md")).toBe("incidents/i-2016-bitfinex.md");
  expect(resolveKbLink("index.md", "ttp-matrix.md")).toBe("ttp-matrix.md");
  expect(resolveKbLink("index.md", "https://example.org")).toBeNull();
  expect(resolveKbLink("index.md", "#section")).toBeNull();
});

test("incident pages list seeds that open in the graph", async () => {
  mocked.kb.mockImplementation(async (c: string) => c === "incidents"
    ? [{ id: "I-2021-COLONIAL", name: "Colonial", date: "2021-05-08", kb: "incidents/i-2021-colonial.md", seeds: [{ kind: "address", value: "bc1qx", role: "seizure", ref: "r", note: "seized" }], seeds_note: null }]
    : []);
  mocked.kbPage.mockResolvedValue({ path: "incidents/i-2021-colonial.md", markdown: "# I-2021-COLONIAL — Colonial\n\nText" });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><KbBrowser path="incidents/i-2021-colonial.md" /></QueryClientProvider>);
  expect(await screen.findByRole("heading", { name: /I-2021-COLONIAL/ })).toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: /open bc1qx in graph/i }));
  expect(actions.openAddress).toHaveBeenCalledWith("bc1qx");
});
