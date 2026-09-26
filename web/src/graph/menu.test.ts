import { menuItems } from "./menu";

test("menu items per kind", () => {
  expect(menuItems("tx").map((i) => i.action)).toEqual([
    "expand-outputs", "expand-inputs", "trace-forward", "trace-backward", "follow-peel", "hide", "remove",
  ]);
  expect(menuItems("address").map((i) => i.action)).toEqual([
    "trace-forward", "trace-backward", "expand-cluster", "select", "hide", "remove",
  ]);
  expect(menuItems("script").map((i) => i.action)).toEqual(["hide", "remove"]);
});
