import { randomInt } from "node:crypto";
import { mkdirSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { test, type Workspace } from "./fixtures";

test.use({ timezoneId: "Asia/Kolkata" });
const password = "LocalCRM!2026";
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/lead-filters") +
  "/screenshots";
mkdirSync(output, { recursive: true });
async function login(page: Page, workspace: Workspace, route = "/app/leads") {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(workspace.phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.goto(route);
  await expect(
    page.getByRole("heading", { name: "Your leads", exact: true }),
  ).toBeVisible();
}
async function lead(
  workspace: Workspace,
  name: string,
  extra: Record<string, unknown> = {},
) {
  const response = await workspace.api.post("/api/leads", {
    data: { name, phone: "+9198" + randomInt(10000000, 99999999), ...extra },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}
async function member(workspace: Workspace, name: string, role = "telecaller") {
  const response = await workspace.api.post("/api/team", {
    data: {
      name,
      phone: "+9196" + randomInt(10000000, 99999999),
      password,
      role,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}
async function more(page: Page) {
  await page.getByRole("button", { name: /^More filters/ }).click();
  return page.getByRole("dialog", { name: "Filter leads", exact: true });
}
async function apply(page: Page) {
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
}

test("clear common controls, draft/cancel, combined chips, saved filters and export agree", async ({
  page,
  workspace,
}) => {
  const setup = await workspace.api.post("/api/real-estate/setup");
  expect(setup.ok(), await setup.text()).toBeTruthy();
  const caller = await member(workspace, "QA Filter Caller");
  const wanted = await lead(workspace, "Panipat matching buyer", {
    city: "Panipat",
    state: "Haryana",
    source: "website",
    category: "apartment",
    stage: "qualified",
    interests: ["River Park"],
  });
  await workspace.api.post("/api/leads/assign", {
    data: { lead_ids: [wanted.id], owner_id: caller.id },
  });
  await lead(workspace, "Panipat other buyer", {
    city: "Panipat",
    state: "Haryana",
    dnd: true,
    category: "plot",
  });
  await lead(workspace, "Delhi website buyer", {
    city: "Delhi",
    source: "website",
  });
  await login(page, workspace);
  await expect(page.locator("tbody tr")).toHaveCount(3);
  await page.getByLabel("Lead source", { exact: true }).selectOption("website");
  await page.getByLabel("Assigned to", { exact: true }).selectOption(caller.id);
  await page.getByLabel("Lead status", { exact: true }).selectOption("new");
  await expect(
    page.getByRole("button", { name: "All leads", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await more(page);
  await page.getByLabel("City", { exact: true }).fill("panipat");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(new URL(page.url()).searchParams.has("city")).toBeFalsy();
  await more(page);
  await expect(page.getByLabel("City", { exact: true })).toHaveValue("");
  await page.getByLabel("City", { exact: true }).fill(" panipat ");
  await page.getByLabel("State / region", { exact: true }).fill("haryana");
  await page
    .getByLabel("Property category", { exact: true })
    .selectOption("apartment");
  await page
    .getByLabel("Property / project interest", { exact: true })
    .fill("park");
  await page
    .getByLabel("Sales stage", { exact: true })
    .selectOption("qualified");
  await page
    .getByLabel("Contact preference", { exact: true })
    .selectOption("false");
  await apply(page);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(
    page.getByRole("button", {
      name: "Remove filter: City: panipat",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".lead-filter-summary")).toContainText(
    "1 lead matches your filters",
  );
  await page
    .getByRole("button", { name: "+ Save filters", exact: true })
    .click();
  await page
    .getByLabel("Filter name", { exact: true })
    .fill("Panipat team buyers");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save filters", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .locator(".lead-filter-summary")
    .getByRole("button", { name: "Clear all filters", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(3);
  await page
    .getByRole("button", { name: "Panipat team buyers", exact: true })
    .click();
  await page.reload();
  await expect(page.getByLabel("Assigned to", { exact: true })).toHaveValue(
    caller.id,
  );
  await expect(page.locator("tbody tr")).toHaveCount(1);
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByLabel("Export filtered leads", { exact: true }).click(),
  ]);
  const stream = await download.createReadStream();
  let csv = "";
  for await (const chunk of stream!) csv += chunk.toString();
  expect(csv).toContain("Panipat matching buyer");
  expect(csv).not.toContain("Panipat other buyer");
  expect(csv).not.toContain("Delhi website buyer");
  await page
    .getByRole("button", { name: "Remove filter: City: panipat", exact: true })
    .click();
  expect(new URL(page.url()).searchParams.has("city")).toBeFalsy();
  await expect(page.locator(".lead-filter-summary")).toContainText(
    "1 lead matches your filters",
  );
  await expect(page.locator("tbody")).toContainText("Panipat matching buyer");
  await page.screenshot({
    path: output + "/applied-filters.png",
    fullPage: true,
  });
});

test("quick views replace conflicting queue choices and reset offers a clear empty-state recovery", async ({
  page,
  workspace,
}) => {
  const caller = await member(workspace, "QA Follow-up Caller");
  const past = await lead(workspace, "Overdue customer", {
    status: "follow-up",
    follow_up: new Date(Date.now() + 5000).toISOString(),
  });
  const future = await lead(workspace, "Upcoming customer", {
    status: "follow-up",
    follow_up: new Date(Date.now() + 86400000).toISOString(),
  });
  await workspace.api.post("/api/leads/assign", {
    data: { lead_ids: [past.id, future.id], owner_id: caller.id },
  });
  await lead(workspace, "Unassigned customer");
  // Let a valid future follow-up become overdue, without bypassing validation.
  await expect
    .poll(
      async () => {
        const result = await workspace.api.get("/api/leads?callback=overdue");
        return (await result.json()).total;
      },
      { timeout: 12000 },
    )
    .toBe(1);
  await login(page, workspace);
  await page
    .getByRole("button", { name: "Overdue follow-ups", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Overdue customer");
  await page.getByRole("button", { name: "Unassigned", exact: true }).click();
  expect(new URL(page.url()).searchParams.has("callback")).toBeFalsy();
  await expect(page.locator("tbody")).toContainText("Unassigned customer");
  await page
    .getByRole("button", { name: "Upcoming follow-ups", exact: true })
    .click();
  expect(new URL(page.url()).searchParams.has("owner_id")).toBeFalsy();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Upcoming customer");
  await page
    .getByRole("button", { name: "Not contacted in 48 hours", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "No leads match these filters",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .locator(".empty")
    .getByRole("button", { name: "Clear all filters", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(3);
  await expect(
    page.getByRole("button", { name: "All leads", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("Lost deals filters and saved views always keep the lost-deal scope", async ({
  page,
  workspace,
}) => {
  const manager = await member(workspace, "QA Lost Manager", "manager");
  for (const [name, reason, source] of [
    ["Budget lost buyer", "Budget too high", "website"],
    ["Location lost buyer", "Wrong location", "manual"],
  ]) {
    const customer = await lead(workspace, name, { source });
    const response = await workspace.api.post(
      `/api/leads/${customer.id}/outcomes`,
      {
        data: {
          outcome: "lost",
          duration: 0,
          notes: reason,
          manager_id: manager.id,
          request_id: "lost-" + customer.id,
        },
      },
    );
    expect(response.status(), await response.text()).toBe(201);
  }
  await lead(workspace, "Still open buyer", { source: "website" });
  await workspace.api.post("/api/saved-views", {
    data: {
      name: "Website new leads",
      kind: "leads",
      filters: { status: "new", source: "website" },
    },
  });
  await login(page, workspace);
  await page.goto("/app/lost");
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await more(page);
  await page.getByLabel("Lost reason contains", { exact: true }).fill("budget");
  await page
    .getByLabel("Marked lost by", { exact: true })
    .selectOption(workspace.user);
  await apply(page);
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Budget lost buyer");
  await page
    .locator(".lead-filter-summary")
    .getByRole("button", { name: "Clear all filters", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Website new leads", exact: true })
    .click();
  expect(new URL(page.url()).searchParams.get("status")).toBe("lost");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).not.toContainText("Still open buyer");
});

test("date presets, inclusive calendar days, invalid ranges and precise saved timestamps", async ({
  page,
  workspace,
}) => {
  await lead(workspace, "Today customer");
  await login(page, workspace);
  for (const preset of ["today", "week", "month"]) {
    await more(page);
    await page.getByLabel("Lead added", { exact: true }).selectOption(preset);
    await expect(
      page.getByLabel("Added through date", { exact: true }),
    ).not.toHaveValue("");
    await apply(page);
    await expect(page.locator("tbody tr")).toHaveCount(1);
  }
  await more(page);
  await page.getByLabel("Lead added", { exact: true }).selectOption("custom");
  await page.getByLabel("Added from date", { exact: true }).fill("2026-03-09");
  await page
    .getByLabel("Added through date", { exact: true })
    .fill("2026-03-08");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "end date on or after",
  );
  await page
    .getByLabel("Added through date", { exact: true })
    .fill("2026-03-09");
  await apply(page);
  const selected = new URL(page.url()).searchParams;
  expect(selected.get("from_date")).toBe("2026-03-08T18:30:00.000Z");
  expect(selected.get("to_date")).toBe("2026-03-09T18:30:00.000Z");
  await page.getByRole("button", { name: /^Remove filter: Added:/ }).click();
  expect(new URL(page.url()).searchParams.has("from_date")).toBeFalsy();
  expect(new URL(page.url()).searchParams.has("to_date")).toBeFalsy();
  const from = "2026-10-24T05:02:03.456Z",
    until = "2026-10-24T06:02:03.456Z";
  await page.goto(
    "/app/leads?" + new URLSearchParams({ from_date: from, to_date: until }),
  );
  await more(page);
  await expect(page.getByLabel("Lead added", { exact: true })).toHaveValue(
    "exact",
  );
  await page.getByLabel("City", { exact: true }).fill("Panipat");
  await apply(page);
  expect(new URL(page.url()).searchParams.get("from_date")).toBe(from);
  expect(new URL(page.url()).searchParams.get("to_date")).toBe(until);
  const saved = await workspace.api.post("/api/saved-views", {
    data: {
      name: "Legacy calendar dates",
      kind: "leads",
      filters: { from_date: "2026-10-01", to_date: "2026-11-01" },
    },
  });
  expect(saved.status()).toBe(201);
  await page.reload();
  await page
    .getByRole("button", { name: "Legacy calendar dates", exact: true })
    .click();
  expect(new URL(page.url()).searchParams.get("from_date")).toBe(
    "2026-09-30T18:30:00.000Z",
  );
  expect(new URL(page.url()).searchParams.get("to_date")).toBe(
    "2026-10-31T18:30:00.000Z",
  );
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("inactive members remain filterable, unavailable selections are visible, pagination and selection reset", async ({
  page,
  workspace,
}) => {
  const caller = await member(workspace, "QA Former Caller");
  const customer = await lead(workspace, "Inactive member customer", {
    source: "broker",
  });
  await workspace.api.post("/api/leads/assign", {
    data: { lead_ids: [customer.id], owner_id: caller.id },
  });
  expect(
    (
      await workspace.api.patch("/api/team/" + caller.id, {
        data: { active: false },
      })
    ).ok(),
  ).toBeTruthy();
  const rows = Array.from(
    { length: 27 },
    (_, i) =>
      `QA paged lead ${i},+9198500000${String(i).padStart(2, "0")},${i ? "manual" : "website"}`,
  );
  const imported = await workspace.api.post("/api/imports?commit=true", {
    multipart: {
      file: {
        name: "filter-pagination.csv",
        mimeType: "text/csv",
        buffer: Buffer.from("name,phone,source\n" + rows.join("\n")),
      },
    },
  });
  expect(imported.ok(), await imported.text()).toBeTruthy();
  await login(page, workspace);
  await page.getByLabel("Assigned to", { exact: true }).selectOption(caller.id);
  await expect(page.getByLabel("Assigned to", { exact: true })).toContainText(
    "QA Former Caller (inactive)",
  );
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.goto("/app/leads?owner_id=00000000-0000-0000-0000-000000000001");
  await expect(page.getByLabel("Assigned to", { exact: true })).toHaveValue(
    "00000000-0000-0000-0000-000000000001",
  );
  await expect(page.getByLabel("Assigned to", { exact: true })).toContainText(
    "Unavailable team member",
  );
  await page
    .getByRole("button", {
      name: "Remove filter: Assigned to: Unavailable member",
      exact: true,
    })
    .click();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(3);
  await page.locator("tbody input[type=checkbox]").first().check();
  await expect(page.locator(".selection-bar")).toBeVisible();
  await page.getByLabel("Lead source", { exact: true }).selectOption("website");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  expect(new URL(page.url()).searchParams.has("page")).toBeFalsy();
  await expect(page.locator(".selection-bar")).toHaveCount(0);
});

test("filter controls, chips and dialog fit 320px to desktop and pass accessibility checks", async ({
  page,
  workspace,
}) => {
  await login(page, workspace);
  await page.getByLabel("Lead source", { exact: true }).selectOption("website");
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    const dialog = await more(page);
    await expect(
      page.getByRole("button", { name: "Apply filters", exact: true }),
    ).toBeInViewport();
    await page.getByLabel("Lead added", { exact: true }).selectOption("custom");
    expect(
      await dialog.evaluate(
        (element) => element.scrollWidth <= element.clientWidth + 1,
      ),
    ).toBeTruthy();
    const axe = await new AxeBuilder({ page }).include("dialog").analyze();
    expect(
      axe.violations.filter((violation) =>
        ["serious", "critical"].includes(violation.impact || ""),
      ),
    ).toEqual([]);
    await page.screenshot({
      path: `${output}/filters-${width}.png`,
      fullPage: true,
    });
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  }
});

test("legacy contact preferences, advanced reset and service failure keep the chosen filters clear", async ({
  page,
  workspace,
}) => {
  await lead(workspace, "Contactable buyer", {
    source: "website",
    city: "Panipat",
  });
  await lead(workspace, "Opted-out buyer", {
    source: "website",
    dnd: true,
    city: "Delhi",
  });
  const saved = await workspace.api.post("/api/saved-views", {
    data: {
      name: "Allowed contacts",
      kind: "leads",
      filters: { source: "website", dnd: false, city: "Panipat" },
    },
  });
  expect(saved.status()).toBe(201);
  await login(page, workspace);
  await page
    .getByRole("button", { name: "Allowed contacts", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  expect(new URL(page.url()).searchParams.get("dnd")).toBe("false");
  await expect(
    page.getByRole("button", {
      name: "Remove filter: Contact preference: Contact allowed",
      exact: true,
    }),
  ).toBeVisible();
  await more(page);
  await page
    .getByRole("button", { name: "Reset more filters", exact: true })
    .click();
  await expect(page.getByLabel("City", { exact: true })).toHaveValue("");
  await expect(
    page.getByLabel("Contact preference", { exact: true }),
  ).toHaveValue("");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(new URL(page.url()).searchParams.get("city")).toBe("Panipat");
  await more(page);
  await page
    .getByRole("button", { name: "Reset more filters", exact: true })
    .click();
  await apply(page);
  await expect(page.getByLabel("Lead source", { exact: true })).toHaveValue(
    "website",
  );
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.route("**/api/leads?*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unavailable",
          message: "Leads are temporarily unavailable",
        },
      }),
    }),
  );
  await page
    .getByLabel("Search lead list", { exact: true })
    .fill("Contactable");
  await expect(page.locator(".lead-filter-summary")).toContainText(
    "Unable to load results. Your filters are kept.",
  );
  await expect(
    page.getByRole("button", {
      name: "Remove filter: Search: Contactable",
      exact: true,
    }),
  ).toBeVisible();
  await page.unroute("**/api/leads?*");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Contactable buyer");
});

test("category and stage options load and retry inside filters without losing a draft", async ({
  page,
  workspace,
}) => {
  expect(
    (await workspace.api.post("/api/real-estate/setup")).ok(),
  ).toBeTruthy();
  await lead(workspace, "Delayed options buyer", {
    city: "Panipat",
    category: "plot",
    stage: "qualified",
  });
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  let unavailable = true;
  await page.route("**/api/definitions", async (route) => {
    await held;
    if (unavailable)
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: {
            code: "options_unavailable",
            message: "Filter options are temporarily unavailable",
          },
        }),
      });
    else await route.continue();
  });
  await login(page, workspace, "/app/leads?category=plot&stage=qualified");
  const dialog = await more(page);
  const category = dialog.getByLabel("Property category", { exact: true });
  const stage = dialog.getByLabel("Sales stage", { exact: true });
  await expect(category).toBeDisabled();
  await expect(stage).toBeDisabled();
  await expect(category).toHaveValue("plot");
  await expect(stage).toHaveValue("qualified");
  await expect(
    dialog.getByRole("status", { name: "Loading form options" }),
  ).toBeVisible();
  await dialog.getByLabel("City", { exact: true }).fill("Panipat");
  release();
  await expect(dialog.getByRole("alert")).toContainText(
    "Filter options are temporarily unavailable",
  );
  await expect(category).toBeDisabled();
  unavailable = false;
  await dialog.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(category).toBeEnabled();
  await expect(stage).toBeEnabled();
  await expect(category.locator("option")).toContainText([
    "All categories",
    "Apartment",
    "Villa",
    "Plot",
  ]);
  await expect(category).toHaveValue("plot");
  await expect(stage).toHaveValue("qualified");
  await expect(dialog.getByLabel("City", { exact: true })).toHaveValue(
    "Panipat",
  );
  expect(new URL(page.url()).searchParams.has("city")).toBeFalsy();
  await apply(page);
  await expect(page.locator("tbody")).toContainText("Delayed options buyer");
  expect(new URL(page.url()).searchParams.get("category")).toBe("plot");
});

test.describe("calendar day boundaries", () => {
  test.use({ timezoneId: "America/New_York" });
  test("a day spanning daylight-saving time uses calendar midnight boundaries", async ({
    page,
    workspace,
  }) => {
    await login(page, workspace);
    await more(page);
    await page.getByLabel("Lead added", { exact: true }).selectOption("custom");
    await page
      .getByLabel("Added from date", { exact: true })
      .fill("2026-03-08");
    await page
      .getByLabel("Added through date", { exact: true })
      .fill("2026-03-08");
    await apply(page);
    const filters = new URL(page.url()).searchParams;
    expect(filters.get("from_date")).toBe("2026-03-08T05:00:00.000Z");
    expect(filters.get("to_date")).toBe("2026-03-09T04:00:00.000Z");
    await expect(page.getByRole("alert")).toHaveCount(0);
  });
});
