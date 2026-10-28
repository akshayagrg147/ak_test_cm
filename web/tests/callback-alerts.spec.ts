import {
  expect,
  request,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { test, type Workspace } from "./fixtures";
import { randomInt, randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";

const password = "LocalCRM!2026";
const phone = () => "+9192" + randomInt(10000000, 99999999);
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/callback-alerts") +
  "/screenshots";
mkdirSync(output, { recursive: true });
interface Person {
  id: string;
  org_id: string;
  name: string;
  phone: string;
}
interface ClientLead {
  id: string;
  name: string;
}
async function apiFor(number: string) {
  const client = await request.newContext({
    baseURL: process.env.E2E_BASE_URL,
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  const auth = await client.post("/api/auth/login", {
    data: { phone: number, password },
  });
  expect(auth.ok()).toBeTruthy();
  const token = (await auth.json()).access_token;
  await client.dispose();
  return request.newContext({
    baseURL: process.env.E2E_BASE_URL,
    extraHTTPHeaders: {
      "X-Requested-With": "TalkoCRM",
      Authorization: "Bearer " + token,
    },
  });
}
async function login(page: Page, number: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(number);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
}
function dateCallbacks(caller: Person, leads: ClientLead[], minutes: number) {
  if (!process.env.E2E_TEST_DATABASE_URL)
    throw new Error("Use the isolated browser runner");
  execFileSync(
    process.env.E2E_PYTHON_BINARY || resolve("../.venv/bin/python"),
    [resolve("../backend/tests/fixtures/callback_alert_browser_seed.py")],
    {
      cwd: resolve("../backend"),
      env: {
        ...process.env,
        DATABASE_URL: process.env.E2E_TEST_DATABASE_URL,
        ENVIRONMENT: "test",
      },
      input: JSON.stringify({
        caller_id: caller.id,
        org_id: caller.org_id,
        lead_ids: leads.map((lead) => lead.id),
        minutes,
      }),
      encoding: "utf8",
    },
  );
}
async function addCallback(
  api: APIRequestContext,
  name: string,
): Promise<ClientLead> {
  const response = await api.post("/api/leads", {
    data: {
      name,
      phone: phone(),
      status: "follow-up",
      follow_up: new Date(Date.now() + 86400000).toISOString(),
    },
  });
  expect(response.status()).toBe(201);
  return response.json();
}
async function prepare(workspace: Workspace) {
  const people: Person[] = [],
    clients: APIRequestContext[] = [];
  for (const name of ["Neha Alert Caller", "Other caller"]) {
    const response = await workspace.api.post("/api/team", {
      data: { name, phone: phone(), password, role: "telecaller" },
    });
    expect(response.status()).toBe(201);
    const person = await response.json();
    people.push(person);
    clients.push(await apiFor(person.phone));
  }
  const own = [
    await addCallback(clients[0], "Anita Sharma"),
    await addCallback(clients[0], "Rahul Verma"),
  ];
  const future = await addCallback(clients[0], "Future callback");
  const other = await addCallback(clients[1], "Colleague private callback");
  dateCallbacks(people[0], own, -60);
  dateCallbacks(people[1], [other], -30);
  return {
    caller: people[0],
    api: clients[0],
    own,
    future,
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
function notificationButton(page: Page) {
  return page.getByRole("button", { name: /^Notifications/ });
}
function badge(page: Page) {
  return notificationButton(page).locator(".callback-alert-count");
}
function inbox(page: Page) {
  return page.getByRole("dialog", { name: "Alerts & reminders", exact: true });
}

test("caller bell keeps overdue callbacks until a result or reschedule, links to the right client and protects privacy", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    await login(page, seed.caller.phone);
    await expect(badge(page)).toHaveText("2");
    await notificationButton(page).click();
    await expect(inbox(page)).toContainText("2 callbacks need attention");
    await expect(inbox(page)).toContainText("Anita Sharma");
    await expect(inbox(page)).not.toContainText("Future callback");
    await expect(inbox(page)).not.toContainText("Colleague private callback");
    await inbox(page)
      .getByRole("button", { name: /Overdue callbacks/ })
      .click();
    await expect(inbox(page).getByRole("link")).toHaveCount(2);
    await accessible(page);
    await page.screenshot({ path: output + "/callback-alerts-1440.png" });
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 1000 });
      await accessible(page);
    }
    await page.screenshot({ path: output + "/callback-alerts-768.png" });
    await page.setViewportSize({ width: 320, height: 1000 });
    const enlarged = await page.addStyleTag({
      content: "html {font-size:200% !important}",
    });
    await accessible(page);
    await enlarged.evaluate((element) =>
      element.parentNode?.removeChild(element),
    );
    await page.setViewportSize({ width: 390, height: 1000 });
    await page.screenshot({ path: output + "/callback-alerts-390.png" });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.keyboard.press("Escape");
    await expect(inbox(page)).toHaveCount(0);
    await expect(notificationButton(page)).toBeFocused();
    await expect(badge(page)).toHaveText("2");
    await notificationButton(page).click();
    await inbox(page)
      .getByRole("link")
      .filter({ hasText: "Anita Sharma" })
      .click();
    await expect(page).toHaveURL(new RegExp("/app/leads/" + seed.own[0].id));
    await expect(inbox(page)).toHaveCount(0);
    await page
      .getByRole("button", { name: "Log a conversation", exact: true })
      .click();
    await page.getByLabel("Outcome", { exact: true }).selectOption("converted");
    await page
      .getByRole("button", { name: "Save outcome", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(badge(page)).toHaveText("1");
    await notificationButton(page).click();
    await expect(inbox(page)).not.toContainText("Anita Sharma");
    await inbox(page)
      .getByRole("link")
      .filter({ hasText: "Rahul Verma" })
      .click();
    await page
      .getByRole("button", { name: "Log a conversation", exact: true })
      .click();
    const next = new Date(Date.now() + 86400000);
    await page
      .getByLabel("Next follow-up", { exact: true })
      .fill(
        new Date(next.getTime() - next.getTimezoneOffset() * 60000)
          .toISOString()
          .slice(0, 16),
      );
    await page
      .getByRole("button", { name: "Save outcome", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(badge(page)).toHaveCount(0);
  } finally {
    await seed.dispose();
  }
});

test("admin bell has exact team counts and all pages; resolving callbacks safely clamps the last page", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    const extra: ClientLead[] = [];
    for (let index = 0; index < 13; index++)
      extra.push(await addCallback(seed.api, `Extra callback ${index + 1}`));
    dateCallbacks(seed.caller, extra, -90);
    await login(page, workspace.phone);
    await expect(badge(page)).toHaveText("16");
    await notificationButton(page).click();
    await expect(inbox(page)).toContainText("1–12 of 16");
    await inbox(page)
      .getByRole("button", { name: "Next", exact: true })
      .click();
    await expect(inbox(page)).toContainText("13–16 of 16");
    await expect(badge(page)).toHaveText("16");
    for (const lead of [...seed.own, ...extra]) {
      expect(
        (
          await seed.api.post(`/api/leads/${lead.id}/outcomes`, {
            data: { outcome: "converted", request_id: randomUUID() },
          })
        ).status(),
      ).toBe(201);
    }
    await inbox(page)
      .getByRole("button", { name: "Refresh alerts", exact: true })
      .click();
    await expect(badge(page)).toHaveText("1");
    await expect(inbox(page)).toContainText("1–1 of 1");
    await expect(inbox(page)).toContainText("Colleague private callback");
    await expect(
      inbox(page).getByRole("button", { name: "Next", exact: true }),
    ).toBeDisabled();
  } finally {
    await seed.dispose();
  }
});

test("bell has an honest loading/error state, supports retry and closes on outside click", async ({
  page,
  workspace,
}) => {
  let release = () => {};
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/notifications/inbox?**", async (route) => {
    const response = await route.fetch();
    await held;
    await route.fulfill({ response });
  });
  try {
    await login(page, workspace.phone);
    await notificationButton(page).click();
    await expect(
      inbox(page).getByRole("status", { name: "Loading", exact: true }),
    ).toBeVisible();
    await expect(
      inbox(page).getByText("You're all caught up", { exact: true }),
    ).toHaveCount(0);
    release();
    await expect(
      inbox(page).getByText("You're all caught up", { exact: true }),
    ).toBeVisible();
    await page.unroute("**/api/notifications/inbox?**");
    await page.route("**/api/notifications/inbox?**", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "temporary",
            message: "Alerts temporarily unavailable",
          },
        }),
      }),
    );
    await inbox(page)
      .getByRole("button", { name: "Refresh alerts", exact: true })
      .click();
    await expect(inbox(page).getByRole("alert")).toContainText(
      "Alerts temporarily unavailable",
    );
    await expect(badge(page)).toHaveText("!");
    await expect(
      inbox(page).getByText("You're all caught up", { exact: true }),
    ).toHaveCount(0);
    await page.unroute("**/api/notifications/inbox?**");
    await inbox(page)
      .getByRole("button", { name: "Try again", exact: true })
      .click();
    await expect(
      inbox(page).getByText("You're all caught up", { exact: true }),
    ).toBeVisible();
    await page.setViewportSize({ width: 320, height: 1000 });
    await accessible(page);
    await page.locator(".workspace-identity").click();
    await expect(inbox(page)).toHaveCount(0);
  } finally {
    release();
  }
});

test("an overdue callback appears automatically without reopening or manually refreshing the bell", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    await login(page, seed.caller.phone);
    await expect(badge(page)).toHaveText("2");
    await notificationButton(page).click();
    await expect(inbox(page)).not.toContainText("Future callback");
    dateCallbacks(seed.caller, [seed.future], -1);
    await expect(badge(page)).toHaveText("3", { timeout: 35000 });
    await expect(inbox(page)).toContainText("Future callback");
  } finally {
    await seed.dispose();
  }
});
