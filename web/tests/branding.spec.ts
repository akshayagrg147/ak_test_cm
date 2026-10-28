import { expect } from "@playwright/test";
import { test } from "./fixtures";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";

const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/viacrm-brand") +
  "/screenshots";
mkdirSync(output, { recursive: true });

test("ViaCRM branding loads on public/login pages and remains readable at mobile widths", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveTitle("ViaCRM — Every lead. A way forward.");
  await expect(page.locator(".public-nav .brand")).toHaveText("ViaCRM");
  await expect(
    page.getByText("VIACRM / WORKSPACE PREVIEW", { exact: true }),
  ).toBeVisible();
  const symbol = page.locator(".public-nav .brand-mark img");
  expect(
    await symbol.evaluate(
      (el) =>
        (el as HTMLImageElement).complete &&
        (el as HTMLImageElement).naturalWidth > 0,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: output + "/public-viacrm-1440.png",
    fullPage: false,
  });
  await page.goto("/login");
  await expect(page).toHaveTitle("ViaCRM · Sign in");
  await expect(page.locator(".login-story .brand")).toHaveText("ViaCRM");
  await page.screenshot({
    path: output + "/login-viacrm-1440.png",
    fullPage: false,
  });
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await expect(
      page.getByRole("button", {
        name: "Sign in to your workspace",
        exact: true,
      }),
    ).toBeVisible();
  }
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  await page.goto("/brand/preview.html");
  expect(
    await page
      .locator("img")
      .evaluateAll((elements) =>
        elements.every(
          (el) =>
            (el as HTMLImageElement).complete &&
            (el as HTMLImageElement).naturalWidth > 0,
        ),
      ),
  ).toBeTruthy();
});

test("ViaCRM is the workspace default while a company's custom brand remains its own", async ({
  page,
  workspace,
}) => {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(workspace.phone);
  await page.getByLabel("Password", { exact: true }).fill("LocalCRM!2026");
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await expect(page.locator(".product-name")).toHaveText("ViaCRM");
  await expect(page).toHaveTitle("ViaCRM · Home");
  await page.screenshot({
    path: output + "/workspace-viacrm-1440.png",
    fullPage: false,
  });
  expect(
    (
      await workspace.api.put("/api/settings", {
        data: { brand_name: "Panipat Client Realty" },
      })
    ).ok(),
  ).toBeTruthy();
  await page.reload();
  await expect(page.locator(".product-name")).toHaveText(
    "Panipat Client Realty",
  );
  await expect(page).toHaveTitle("Panipat Client Realty · Home");
});
