import { expect, test } from "@playwright/test";
import { ADDRESS, TXID, mockApi } from "./fixtures";

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

test("entering an address runs the automatic analysis and opens its graph", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("searchbox").fill(ADDRESS);
  await page.getByRole("searchbox").press("Enter");
  await expect(page).toHaveURL(new RegExp(`#/analysis/${ADDRESS}$`));
  const verdict = page.getByRole("region", { name: "Verdict" });
  await expect(verdict.getByText(/directly from LockBit/)).toBeVisible();
  await expect(verdict.getByText("preliminary: tracing still running")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Destinations of funds" }).getByRole("button", { name: "Example Exchange" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save as case" })).toBeEnabled();
  await page.getByRole("button", { name: "Open in graph" }).click();
  await expect(page.getByTestId("graph-stats")).toHaveText("1 txs · 2 addresses · 2 edges · 1 stops");
});
