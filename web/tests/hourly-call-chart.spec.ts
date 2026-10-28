import {
  expect,
  request,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { test, type Workspace } from "./fixtures";
import AxeBuilder from "@axe-core/playwright";
import { randomInt, randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";

const password = "LocalCRM!2026";
const phone = () => "+9193" + randomInt(10000000, 99999999);
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/hourly-call-chart") +
  "/screenshots";
mkdirSync(output, { recursive: true });

async function login(page: Page, number: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(number);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.goto("/app/reports");
}
async function prepare(workspace: Workspace) {
  const callers: { id: string; phone: string }[] = [];
  const clients: APIRequestContext[] = [];
  for (const [index, name] of ["Hourly caller", "Other caller"].entries()) {
    const user = await workspace.api.post("/api/team", {
      data: { name, phone: phone(), role: "telecaller", password },
    });
    expect(user.status()).toBe(201);
    const caller = await user.json();
    callers.push(caller);
    const client = await request.newContext({
      baseURL: process.env.E2E_BASE_URL,
      extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
    });
    const auth = await client.post("/api/auth/login", {
      data: { phone: caller.phone, password },
    });
    expect(auth.ok()).toBeTruthy();
    const token = (await auth.json()).access_token;
    await client.dispose();
    const api = await request.newContext({
      baseURL: process.env.E2E_BASE_URL,
      extraHTTPHeaders: {
        "X-Requested-With": "TalkoCRM",
        Authorization: "Bearer " + token,
      },
    });
    clients.push(api);
    const lead = await api.post("/api/leads", {
      data: { name: `Hourly client ${index + 1}`, phone: phone() },
    });
    expect(lead.status()).toBe(201);
    const saved = await lead.json();
    const hours = index === 0 ? [3, 3, 7] : [12];
    const calls = hours.map((hour, position) => {
      const started = new Date(Date.now() - 86400000);
      started.setUTCHours(hour, position === 1 ? 50 : 35, 0, 0);
      return {
        device_call_id: `hourly-${position}`,
        phone: saved.phone,
        direction: "outgoing",
        result: "answered",
        started_at: started.toISOString(),
        duration: 60,
      };
    });
    expect(
      (
        await api.post("/api/phone-calls/sync", {
          data: { device_id: "hourly-qa", calls },
        })
      ).ok(),
    ).toBeTruthy();
    if (index === 0) {
      const history = await api.get("/api/phone-calls");
      expect(history.ok()).toBeTruthy();
      const linked = (await history.json()).items[0].id;
      for (const association of [{ phone_call_id: linked }, {}]) {
        const outcome = await api.post(`/api/leads/${saved.id}/outcomes`, {
          data: {
            outcome: "not-picked",
            duration: 60,
            request_id: randomUUID(),
            ...association,
          },
        });
        expect(outcome.status(), await outcome.text()).toBe(201);
      }
    }
  }
  return {
    caller: callers[0],
    callerApi: clients[0],
    dispose: () => Promise.all(clients.map((client) => client.dispose())),
  };
}
async function accessible(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact || ""),
    ),
  ).toEqual([]);
}
async function matchesChart(
  page: Page,
  hours: { hour: number; calls: number }[],
) {
  const chart = page.getByRole("figure", {
    name: "Calls by hour",
    exact: true,
  });
  await expect(chart.getByRole("button")).toHaveCount(24);
  for (const hour of hours) {
    const column = chart.getByRole("button").nth(hour.hour);
    await expect(column.locator(".call-hourly-well strong")).toHaveText(
      hour.calls.toLocaleString(),
    );
    const box = await column.locator(".call-hourly-bar").boundingBox();
    expect(box).not.toBeNull();
    if (hour.calls === 0) expect(box!.height).toBe(0);
    else expect(box!.height).toBeGreaterThan(0);
  }
}

test("hourly report shows exact clock-hour counts, true zeroes, deduplicated calls and employee filtering", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    const response = await workspace.api.get("/api/analytics");
    const data = await response.json();
    expect(data.metrics.calls).toBe(5);
    expect(
      data.hourly.reduce(
        (sum: number, row: { calls: number }) => sum + row.calls,
        0,
      ),
    ).toBe(5);
    expect(data.hourly[9].calls).toBeGreaterThanOrEqual(2);
    await login(page, workspace.phone);
    const chart = page.getByRole("figure", {
      name: "Calls by hour",
      exact: true,
    });
    await expect(chart.locator("figcaption strong")).toHaveText("5 calls");
    await expect(chart.locator("figcaption")).toContainText("Asia/Kolkata");
    await expect(chart.getByRole("button").first()).toHaveAccessibleName(
      /^12 AM.*calls?$/,
    );
    await expect(chart.getByRole("button").nth(12)).toHaveAccessibleName(
      /^12 PM.*calls?$/,
    );
    await expect(chart.getByRole("button").last()).toHaveAccessibleName(
      /^11 PM.*calls?$/,
    );
    await expect(chart.getByRole("button").first()).toHaveAttribute(
      "title",
      /^12 AM – 1 AM:/,
    );
    await expect(chart.getByRole("button").last()).toHaveAttribute(
      "title",
      /^11 PM – 12 AM:/,
    );
    await matchesChart(page, data.hourly);
    const zero = data.hourly.find((row: { calls: number }) => row.calls === 0);
    await chart.getByRole("button").nth(zero.hour).press("Enter");
    await expect(chart.locator(".call-hourly-selection")).toContainText(
      "No calls recorded for this hour.",
    );
    await chart.getByText("View hourly data", { exact: true }).click();
    const table = chart.getByRole("table", {
      name: "Hourly call counts · Asia/Kolkata",
    });
    await expect(table.getByRole("row")).toHaveCount(25);
    const counts = await table.locator("tbody td").allTextContents();
    expect(
      counts.reduce((sum, value) => sum + Number(value.replaceAll(",", "")), 0),
    ).toBe(5);
    await accessible(page);
    await chart.getByText("View hourly data", { exact: true }).click();
    await chart.screenshot({ path: output + "/hourly-admin-1440.png" });
    await page
      .getByLabel("Report employee", { exact: true })
      .selectOption(seed.caller.id);
    await expect(chart.locator("figcaption strong")).toHaveText("4 calls");
    const own = await workspace.api.get("/api/analytics", {
      params: { owner_id: seed.caller.id },
    });
    await matchesChart(page, (await own.json()).hourly);
    await page.getByLabel("Report from date").fill("2000-01-01");
    await page.getByLabel("Report end date").fill("2000-01-02");
    await expect(
      chart.getByText("No calls in this period", { exact: true }),
    ).toBeVisible();
    await expect(chart.locator("figcaption strong")).toHaveText("0 calls");
  } finally {
    await seed.dispose();
  }
});

test("empty hourly reports have no phantom bars and retain all 24 zero-count table rows", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  const chart = page.getByRole("figure", {
    name: "Calls by hour",
    exact: true,
  });
  await expect(
    chart.getByText("No calls in this period", { exact: true }),
  ).toBeVisible();
  await expect(chart.locator(".call-hourly-bar")).toHaveCount(0);
  await chart.getByText("View hourly data", { exact: true }).click();
  const table = chart.getByRole("table", {
    name: "Hourly call counts · Asia/Kolkata",
  });
  await expect(table.getByRole("row")).toHaveCount(25);
  expect(await table.locator("tbody td").allTextContents()).toEqual(
    Array(24).fill("0"),
  );
  await page.setViewportSize({ width: 320, height: 1000 });
  await accessible(page);
});

test("telecaller hourly charts stay private and readable on mobile and with doubled text", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    await login(page, seed.caller.phone);
    const chart = page.getByRole("figure", {
      name: "Calls by hour",
      exact: true,
    });
    await expect(chart.locator("figcaption strong")).toHaveText("4 calls");
    await expect(
      page.getByLabel("Report employee", { exact: true }),
    ).toHaveCount(0);
    const own = await seed.callerApi.get("/api/analytics");
    await matchesChart(page, (await own.json()).hourly);
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await accessible(page);
    }
    await page.setViewportSize({ width: 320, height: 1000 });
    const enlarged = await page.addStyleTag({
      content: "html {font-size:200% !important}",
    });
    await accessible(page);
    await enlarged.evaluate((element) =>
      element.parentNode?.removeChild(element),
    );
    await page.setViewportSize({ width: 390, height: 1000 });
    await chart.screenshot({ path: output + "/hourly-caller-390.png" });
  } finally {
    await seed.dispose();
  }
});
