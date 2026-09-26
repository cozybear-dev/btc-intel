import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the workbench title", () => {
  render(<App />);
  expect(screen.getByText(/btc-intel workbench/i)).toBeInTheDocument();
});
