import { expect, test } from "@playwright/test";
import { TXID, mockApi } from "./fixtures";

test("search, expand, inspect, save and reload a case", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("searchbox").fill(TXID);
  await page.getByRole("searchbox").press("Enter");
  await expect(page.getByTestId("graph-stats")).toHaveText("1 txs · 3 addresses · 3 edges · 0 stops");
  await expect(page.getByRole("link", { name: "H-CHG" })).toBeVisible();

  await page.getByRole("button", { name: "Expand outputs", exact: true }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText("2 txs · 4 addresses · 5 edges · 0 stops");

  await page.getByRole("tab", { name: "Case" }).click();
  await page.getByLabel("Case name").fill("E2E case");
  await page.getByRole("button", { name: /^Save/ }).click();
  await expect(page.getByRole("button", { name: "E2E case", exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("graph-stats")).toHaveText("0 txs · 0 addresses · 0 edges · 0 stops");
  await page.getByRole("tab", { name: "Case" }).click();
  await page.getByRole("button", { name: "E2E case", exact: true }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText("2 txs · 4 addresses · 5 edges · 0 stops");
});

test("knowledge base view is reachable", async ({ page }) => {
  await mockApi(page);
  await page.goto("/#/kb");
  await expect(page.getByRole("link", { name: "TTP matrix" })).toBeVisible();
});
