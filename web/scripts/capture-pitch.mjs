/* global document, innerWidth */
import { chromium, expect } from "@playwright/test";
import { mkdirSync } from "node:fs";
import console from "node:console";
const output = "../artifacts/redesign/pitch";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
async function ready() {
  await expect(page.locator("#workspace-main h1")).toBeVisible();
  await expect(page.locator("#workspace-main .skeletons")).toHaveCount(0);
  await expect(page.locator("#workspace-main .error-box")).toHaveCount(0);
  await page.evaluate(() => document.fonts.ready);
}
try {
  await page.goto("http://localhost:5173/login");
  await page.getByLabel("Phone number").fill("+919900000007");
  await page.getByLabel("Password", { exact: true }).fill("LocalCRM!2026");
  await page
    .getByRole("button", { name: "Sign in to your workspace", exact: true })
    .click();
  await page.waitForURL("**/app/overview");
  const routes = [
    "overview",
    "leads",
    "tasks",
    "phone-calls",
    "lost",
    "reports",
    "attendance",
    "approvals",
    "team",
    "payroll",
    "automations",
    "integrations",
    "audit",
    "backups",
    "settings",
    "security",
  ];
  for (const width of [1440, 360]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of routes) {
      await page.goto("http://localhost:5173/app/" + route);
      await ready();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 1,
      );
      if (overflow) throw new Error("Page overflow: " + route + " " + width);
      await page.screenshot({
        path: `${output}/${route}-${width}.png`,
        fullPage: true,
      });
      console.log("Captured", route, width);
    }
  }
  await page.goto("http://localhost:5173/app/leads");
  await ready();
  await page.locator("tbody .name-cell").first().click();
  await ready();
  await page.screenshot({
    path: `${output}/lead-detail-360.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: `${output}/lead-detail-1440.png`,
    fullPage: true,
  });
  await page.goto("http://localhost:5173/app/overview");
  await ready();
  await page.screenshot({ path: `${output}/overview-preview.png` });
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "35 screenshots captured; all 16 pages contained at 1440 and 360px; no browser exceptions or page errors.",
  );
} finally {
  await browser.close();
}
