import { expect, request, type Page } from "@playwright/test";
import { test, type Workspace } from "./fixtures";
import type { Lead, User } from "../src/types";
import { execFileSync } from "node:child_process";
import { randomInt } from "node:crypto";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";

const password = "LocalCRM!2026";
const number = () => "+9194" + randomInt(10000000, 99999999);
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/dashboard") + "/screenshots";
mkdirSync(output, { recursive: true });

async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Sign in to your workspace", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/(overview|platform)/);
}
async function apiFor(phone: string) {
  const client = await request.newContext({
    baseURL: process.env.E2E_BASE_URL,
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  const signed = await client.post("/api/auth/login", {
    data: { phone, password },
  });
  expect(signed.ok()).toBeTruthy();
  const token = (await signed.json()).access_token;
  await client.dispose();
  return request.newContext({
    baseURL: process.env.E2E_BASE_URL,
    extraHTTPHeaders: {
      "X-Requested-With": "TalkoCRM",
      Authorization: "Bearer " + token,
    },
  });
}
async function prepare(workspace: Workspace) {
  expect(
    (await workspace.api.post("/api/real-estate/setup")).ok(),
  ).toBeTruthy();
  const callers: User[] = [];
  for (const name of ["Neha QA Caller", "Other colleague private"]) {
    const result = await workspace.api.post("/api/team", {
      data: { name, phone: number(), role: "telecaller", password },
    });
    expect(result.status()).toBe(201);
    callers.push(await result.json());
  }
  const callerApi = await apiFor(callers[0].phone),
    otherApi = await apiFor(callers[1].phone);
  const leads: Lead[] = [];
  const names = [
    "Anita Sharma",
    "Rahul Verma",
    "Simran Kaur",
    "Nitin Gupta",
    "Meera Saini",
    "Vikas Bhatia",
  ];
  const stages = ["qualified", "new", "site_visit", "proposal", "new", "won"];
  for (let i = 0; i < names.length; i++) {
    const result = await callerApi.post("/api/leads", {
      data: {
        name: names[i],
        phone: number(),
        city: "Panipat",
        source: ["website", "referral", "manual"][i % 3],
        stage: stages[i],
      },
    });
    expect(result.status()).toBe(201);
    leads.push(await result.json());
  }
  const other = await otherApi.post("/api/leads", {
    data: { name: "Other colleague client", phone: number(), city: "Panipat" },
  });
  expect(other.status()).toBe(201);
  const second = await other.json();
  const calls = Array.from({ length: 21 }, (_, index) => ({
    device_call_id: "dash-" + index,
    phone: leads[index % leads.length].phone,
    direction: "outgoing",
    result: index % 4 === 0 ? "missed" : "answered",
    started_at: new Date(
      Date.now() - (index % 5) * 86400000 - 60000,
    ).toISOString(),
    duration: index % 4 === 0 ? 0 : 120 + index * 5,
  }));
  expect(
    (
      await callerApi.post("/api/phone-calls/sync", {
        data: { device_id: "dashboard-demo", calls },
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await otherApi.post("/api/phone-calls/sync", {
        data: {
          device_id: "other-dashboard",
          calls: [
            {
              device_call_id: "private-1",
              phone: second.phone,
              direction: "incoming",
              result: "answered",
              started_at: new Date().toISOString(),
              duration: 45,
            },
          ],
        },
      })
    ).ok(),
  ).toBeTruthy();
  const database = process.env.E2E_TEST_DATABASE_URL;
  if (!database)
    throw new Error("Dashboard fixtures require the isolated runner");
  execFileSync(
    process.env.E2E_PYTHON_BINARY || resolve("../.venv/bin/python"),
    [resolve("../backend/tests/fixtures/dashboard_browser_seed.py")],
    {
      cwd: resolve("../backend"),
      env: { ...process.env, DATABASE_URL: database, ENVIRONMENT: "test" },
      input: JSON.stringify({
        caller_id: callers[0].id,
        org_id: callers[0].org_id,
        lead_ids: leads.map((lead) => lead.id),
      }),
      encoding: "utf8",
    },
  );
  for (const [index, title] of [
    "Discuss home loan documents",
    "Confirm property viewing",
    "Share revised property shortlist",
  ].entries()) {
    const saved = await workspace.api.post("/api/tasks", {
      data: {
        title,
        owner_id: callers[0].id,
        lead_id: leads[index].id,
        due_at: new Date(Date.now() + (index + 1) * 3600000).toISOString(),
      },
    });
    expect(saved.status()).toBe(201);
  }
  expect(
    (
      await workspace.api.post("/api/tasks", {
        data: {
          title: "Review today's visit briefs",
          due_at: new Date(Date.now() + 3600000).toISOString(),
        },
      })
    ).status(),
  ).toBe(201);
  await otherApi.dispose();
  return { caller: callers[0], other: callers[1], callerApi, leads };
}
async function accessible(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  expect(
    result.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact || ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
}
function metric(page: Page, name: string) {
  return page
    .locator(".crm-dashboard-stats .stat")
    .filter({ has: page.getByText(name, { exact: true }) })
    .locator(":scope > strong");
}

test("admin dashboard uses persisted counts, chart controls, employee scope and working client links", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    await login(page, workspace.phone);
    await expect(metric(page, "Team calls logged")).toHaveText("22");
    await expect(metric(page, "Follow-ups overdue")).toHaveText("2");
    await expect(
      page.getByRole("heading", {
        name: "Enquiry & calling activity",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByText("View chart data", { exact: true }).click();
    const table = page.getByRole("table", {
      name: "Activity in the selected period",
      exact: true,
    });
    await expect(table.getByRole("row")).toHaveCount(8);
    await page.getByRole("button", { name: "Enquiries", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Enquiries", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await accessible(page);
    await page.getByText("View chart data", { exact: true }).click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: output + "/admin-dashboard-1440.png",
      fullPage: false,
    });
    await page.screenshot({
      path: output + "/admin-dashboard-full.png",
      fullPage: true,
    });
    await page
      .getByLabel("Dashboard team member", { exact: true })
      .selectOption(seed.caller.id);
    await expect(metric(page, "Team calls logged")).toHaveText("21");
    await expect(page.locator(".crm-priority-list")).not.toContainText(
      "Other colleague client",
    );
    await page.getByRole("button", { name: "Today", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Today", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    const response = await workspace.api.get(
      "/api/dashboard?days=1&owner_id=" + seed.caller.id,
    );
    const expected = await response.json();
    await expect(metric(page, "Team calls logged")).toHaveText(
      String(expected.metrics.calls),
    );
    await page
      .getByRole("button", { name: "Last 30 days", exact: true })
      .click();
    await expect(metric(page, "Team calls logged")).toHaveText("21");
    await page
      .locator(".crm-priority-list")
      .getByRole("link")
      .filter({ hasText: seed.leads[0].name })
      .click();
    await expect(page).toHaveURL(new RegExp("/app/leads/" + seed.leads[0].id));
  } finally {
    await seed.callerApi.dispose();
  }
});

test("telecaller gets a personal dashboard, private clients and calls, readable mobile charts and direct next steps", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    await login(page, seed.caller.phone);
    await expect(
      page.getByRole("heading", {
        name: "Your calling day, made simple.",
        exact: true,
      }),
    ).toBeVisible();
    await expect(metric(page, "My assigned clients")).toHaveText("6");
    await expect(metric(page, "My calls logged")).toHaveText("21");
    await expect(
      page.getByLabel("Dashboard team member", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "Team calling activity", exact: true }),
    ).toHaveCount(0);
    await expect(page.getByText("Booking value", { exact: true })).toHaveCount(
      0,
    );
    await expect(page.locator(".crm-dashboard")).not.toContainText(
      "Other colleague client",
    );
    await expect(page.locator(".crm-task-list").first()).toContainText(
      "Discuss home loan documents",
    );
    await accessible(page);
    await page.screenshot({
      path: output + "/telecaller-dashboard-1440.png",
      fullPage: false,
    });
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 1000 });
      await accessible(page);
    }
    await page.setViewportSize({ width: 320, height: 1000 });
    const enlarged = await page.addStyleTag({
      content: "html { font-size: 200% !important; }",
    });
    await accessible(page);
    await enlarged.evaluate((element) =>
      element.parentNode?.removeChild(element),
    );
    await page.setViewportSize({ width: 768, height: 1000 });
    await page.screenshot({
      path: output + "/telecaller-dashboard-768.png",
      fullPage: false,
    });
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.screenshot({
      path: output + "/telecaller-dashboard-390.png",
      fullPage: true,
    });
    await page.getByRole("link", { name: "My clients", exact: false }).click();
    await expect(page).toHaveURL(/\/app\/leads$/);
    await expect(
      page.getByText("Other colleague client", { exact: true }),
    ).toHaveCount(0);
  } finally {
    await seed.callerApi.dispose();
  }
});

test("empty dashboard is honest and a temporary request failure can be retried without losing the selected period", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  await expect(metric(page, "New enquiries")).toHaveText("0");
  await expect(
    page.getByText("No calls logged in this period.", { exact: true }),
  ).toBeVisible();
  await page.route("**/api/dashboard?days=30**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "temporary",
          message: "Dashboard temporarily unavailable",
        },
      }),
    }),
  );
  await page.getByRole("button", { name: "Last 30 days", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Dashboard temporarily unavailable",
  );
  await expect(
    page.getByRole("button", { name: "Last 30 days", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.unroute("**/api/dashboard?days=30**");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(metric(page, "New enquiries")).toHaveText("0");
  await expect(
    page.getByRole("button", { name: "Last 30 days", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.setViewportSize({ width: 320, height: 1000 });
  await accessible(page);
});

test("super admin sees company and subscription charts without changing company management", async ({
  page,
}) => {
  const owner = await apiFor("+919900000001");
  const companyName = "Dashboard trial QA " + Date.now();
  const created = await owner.post("/api/platform/organizations", {
    data: {
      name: companyName,
      industry: "real_estate",
      admin: {
        name: "Trial QA Administrator",
        phone: number(),
        password,
        role: "admin",
      },
    },
  });
  expect(created.status()).toBe(201);
  const identity = (await created.json()).organization.id;
  try {
    await login(page, "+919900000001");
    await expect(
      page.getByRole("heading", { name: "Subscription health", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Company team sizes", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Company directory", exact: true }),
    ).toBeVisible();
    await accessible(page);
    await page.screenshot({
      path: output + "/super-admin-dashboard-1440.png",
      fullPage: false,
    });
    await page.setViewportSize({ width: 390, height: 1000 });
    await accessible(page);
    await page
      .getByRole("button", { name: "Create company", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Cancel", exact: true })
      .click();
  } finally {
    expect(
      (
        await owner.delete("/api/platform/organizations/" + identity, {
          params: { confirmation: companyName },
        })
      ).ok(),
    ).toBeTruthy();
    await owner.dispose();
  }
});
