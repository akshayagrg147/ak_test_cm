import { execFileSync } from "node:child_process";
import { randomInt } from "node:crypto";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, request, type Page } from "@playwright/test";
import { test, type Workspace } from "./fixtures";

const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/office-call-pay") +
  "/screenshots";
mkdirSync(output, { recursive: true });
const password = "LocalCRM!2026";
async function login(page: Page, workspace: Workspace) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(workspace.phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Sign in to your workspace", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.goto("/app/payroll");
  await expect(
    page.getByRole("heading", { name: "Payroll estimates", exact: true }),
  ).toBeVisible();
}
async function employee(workspace: Workspace) {
  const response = await workspace.api.post("/api/team", {
    data: {
      name: "QA Office Caller",
      phone: "+9193" + randomInt(10000000, 99999999),
      password,
      role: "telecaller",
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}

test("office approval and synced call time produce separate rates, a daily breakdown and matching CSV", async ({
  page,
  workspace,
}) => {
  const caller = await employee(workspace);
  const created = await workspace.api.post("/api/leads", {
    data: {
      name: "Payroll call buyer",
      phone: "+9192" + randomInt(10000000, 99999999),
    },
  });
  expect(created.status()).toBe(201);
  const lead = await created.json();
  expect(
    (
      await workspace.api.post("/api/leads/assign", {
        data: { lead_ids: [lead.id], owner_id: caller.id },
      })
    ).ok(),
  ).toBeTruthy();
  const databaseURL =
    process.env.E2E_TEST_DATABASE_URL ||
    "postgresql+psycopg://127.0.0.1:55432/talkocrm_browser_test";
  const seeded = JSON.parse(
    execFileSync(
      process.env.E2E_PYTHON_BINARY || resolve("../.venv/bin/python"),
      [resolve("../backend/tests/fixtures/payroll_browser_seed.py")],
      {
        cwd: resolve("../backend"),
        env: { ...process.env, DATABASE_URL: databaseURL, ENVIRONMENT: "test" },
        input: JSON.stringify({
          admin_id: workspace.user,
          employee_id: caller.id,
          lead_id: lead.id,
        }),
        encoding: "utf8",
      },
    ),
  );
  const callerApi = await request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  try {
    const auth = await callerApi.post("/api/auth/login", {
      data: { phone: caller.phone, password },
    });
    expect(auth.ok()).toBeTruthy();
    const token = (await auth.json()).access_token;
    const sync = {
      device_id: "payroll-browser",
      calls: [
        {
          device_call_id: "payroll-1",
          phone: lead.phone,
          started_at: seeded.call_start,
          duration: 7200,
          direction: "outgoing",
          result: "answered",
        },
      ],
    };
    const headers = { Authorization: "Bearer " + token };
    const first = await callerApi.post("/api/phone-calls/sync", {
      headers,
      data: sync,
    });
    expect(first.ok(), await first.text()).toBeTruthy();
    expect((await first.json()).created).toBe(1);
    await login(page, workspace);
    await page.getByLabel("Payroll month", { exact: true }).fill(seeded.month);
    const row = page.getByRole("row").filter({ hasText: caller.name });
    await row.getByRole("button", { name: "Edit rate", exact: true }).click();
    await page
      .getByLabel("Calculate salary using", { exact: true })
      .selectOption("office_calls");
    await page
      .getByLabel("Office hourly rate (₹)", { exact: true })
      .fill("100");
    await page
      .getByLabel("Calling hourly rate (₹)", { exact: true })
      .fill("150");
    await page
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(row).toContainText("₹300.00");
    await expect(row).toContainText("8h 00m awaiting approval");
    await page.goto("/app/approvals");
    await page
      .getByRole("row")
      .filter({ hasText: caller.name })
      .getByRole("button", { name: "Review", exact: true })
      .click();
    await page.getByLabel("Decision", { exact: true }).selectOption("approved");
    await page
      .getByRole("button", { name: "Record decision", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.goto("/app/payroll");
    await page.getByLabel("Payroll month", { exact: true }).fill(seeded.month);
    await expect(row).toContainText("₹900.00");
    await row
      .getByRole("button", { name: "View breakdown", exact: true })
      .click();
    const detail = page.getByRole("dialog", {
      name: "Salary breakdown · " + caller.name,
      exact: true,
    });
    await expect(detail.locator(".pay-calculation")).toContainText("6h 00m");
    await expect(detail.locator(".pay-calculation")).toContainText("2h 00m");
    await expect(detail.locator(".pay-calculation")).toContainText("₹600.00");
    await expect(detail.locator(".pay-calculation")).toContainText("₹300.00");
    await expect(detail.locator("tbody")).toContainText(seeded.day);
    const axe = await new AxeBuilder({ page }).include("dialog").analyze();
    expect(
      axe.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact || ""),
      ),
    ).toEqual([]);
    await page.screenshot({
      path: output + "/salary-6-office-2-call.png",
      fullPage: true,
    });
    await detail.getByRole("button", { name: "Close", exact: true }).click();
    // A later duration update changes the same call rather than adding another salary item.
    sync.calls[0].duration = 9000;
    expect(
      (
        await callerApi.post("/api/phone-calls/sync", { headers, data: sync })
      ).ok(),
    ).toBeTruthy();
    const retry = await callerApi.post("/api/phone-calls/sync", {
      headers,
      data: sync,
    });
    expect((await retry.json()).created).toBe(0);
    await page.reload();
    await expect(row).toContainText("₹925.00");
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page
        .getByRole("button", { name: "Export estimate", exact: true })
        .click(),
    ]);
    const stream = await download.createReadStream();
    let csv = "";
    for await (const chunk of stream!) csv += chunk.toString();
    expect(csv).toContain("office_calls");
    expect(csv).toContain("550.00,375.00,925.00");
    await page.screenshot({
      path: output + "/salary-estimates.png",
      fullPage: true,
    });
  } finally {
    await callerApi.dispose();
  }
});

test("pay settings retain values after failure and payroll remains usable at mobile widths", async ({
  page,
  workspace,
}) => {
  const caller = await employee(workspace);
  await login(page, workspace);
  await page
    .getByLabel("Search payroll employees", { exact: true })
    .fill(caller.name);
  const row = page.getByRole("row").filter({ hasText: caller.name });
  await row.getByRole("button", { name: "Edit rate", exact: true }).click();
  await page
    .getByLabel("Calculate salary using", { exact: true })
    .selectOption("office_calls");
  await page
    .getByLabel("Office hourly rate (₹)", { exact: true })
    .fill("125.25");
  await page
    .getByLabel("Calling hourly rate (₹)", { exact: true })
    .fill("200.50");
  await page.route("**/api/payroll/profiles/*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unavailable",
          message: "Pay settings temporarily unavailable",
        },
      }),
    }),
  );
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "temporarily unavailable",
  );
  await expect(
    page.getByLabel("Calling hourly rate (₹)", { exact: true }),
  ).toHaveValue("200.50");
  await page.unroute("**/api/payroll/profiles/*");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(row).toContainText("Office + calling");
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await row
      .getByRole("button", { name: "View breakdown", exact: true })
      .click();
    const detail = page.getByRole("dialog");
    expect(
      await detail.evaluate(
        (element) => element.scrollWidth <= element.clientWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `${output}/salary-breakdown-${width}.png`,
      fullPage: true,
    });
    await page.keyboard.press("Escape");
    await row.getByRole("button", { name: "Edit rate", exact: true }).click();
    await expect(
      page.getByLabel("Calling hourly rate (₹)", { exact: true }),
    ).toHaveValue("200.50");
    const axe = await new AxeBuilder({ page }).include("dialog").analyze();
    expect(
      axe.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact || ""),
      ),
    ).toEqual([]);
    await page.keyboard.press("Escape");
  }
});
