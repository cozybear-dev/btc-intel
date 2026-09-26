import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../state/actions", () => ({ search: vi.fn(), openAddress: vi.fn() }));

import * as actions from "../state/actions";
import SearchBar from "./SearchBar";

test("submits on Enter and lists tag hits", async () => {
  (actions.search as ReturnType<typeof vi.fn>).mockResolvedValue({
    kind: "text", query: "lazarus",
    tags: [{ id: 1, address: "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", label: "Lazarus Group", category: "individual", abuse: "sanctioned", actor: null, confidence: "authority_data", confidence_level: 60, source: "s", pack: "ofac_sdn", is_cluster_definer: false, lastmod: null, created_by: "import" }],
  });
  render(<SearchBar />);
  await userEvent.type(screen.getByRole("searchbox"), "lazarus{Enter}");
  expect(actions.search).toHaveBeenCalledWith("lazarus");
  await userEvent.click(await screen.findByRole("button", { name: /Lazarus Group/ }));
  expect(actions.openAddress).toHaveBeenCalledWith("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa");
});
