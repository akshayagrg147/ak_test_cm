import { expect, type Page } from "@playwright/test";
import { test } from "./fixtures";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
const screenshots =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/redesign") + "/screenshots";
mkdirSync(screenshots, { recursive: true });
async function login(
  page: Page,
  phone = "+919900000002",
  password = "LocalCRM!2026",
) {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview|\/app\/platform/);
  await expect(page.locator(".skeletons")).toHaveCount(0);
}
test("public site, interactive preview, FAQ and truthful contact setup", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Every opportunity.",
  );
  await page
    .getByRole("button", { name: "Team activity", exact: true })
    .click();
  await expect(page.locator(".preview-stats")).toContainText("Tasks completed");
  await page
    .getByText("How does a company subscription work?", { exact: true })
    .click();
  await expect(
    page.getByText(
      "The super admin verifies receipt before activating the subscription.",
      {
        exact: false,
      },
    ),
  ).toBeVisible();
  await expect(page.locator("#contact")).toContainText(
    "Contact details are being configured",
  );
  await page.screenshot({
    path: screenshots + "/public-1440.png",
    fullPage: true,
  });
});
test("admin creates, edits, logs an outcome, adds a note and completes a task through the UI", async ({
  page,
}) => {
  await login(page);
  await page.screenshot({
    path: screenshots + "/overview-1440.png",
    fullPage: true,
  });
  await page
    .getByRole("navigation", { name: "Work areas", exact: true })
    .getByRole("link", { name: "Sales", exact: true })
    .click();
  await page.getByRole("link", { name: "Leads", exact: true }).click();
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  const name = "Browser Journey " + Date.now();
  const phone = "+9198" + String(Date.now()).slice(-8);
  await page.getByLabel("Customer / buyer name").fill(name);
  await page.getByLabel("Phone number", { exact: false }).last().fill(phone);
  await page.getByLabel("City", { exact: true }).fill("Pune");
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("link", { name: new RegExp(name) })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name, exact: true, level: 1 }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Log a conversation" }).click();
  await page.getByLabel("Outcome").selectOption("converted");
  await page.getByLabel("Declared duration").fill("120");
  await page.getByLabel("Order value").fill("1250.50");
  await page
    .getByLabel("Notes / lost reason")
    .fill("Customer confirmed the project.");
  await page.getByRole("button", { name: "Save outcome" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".lead-profile")).toContainText("converted");
  await page.getByRole("button", { name: "Notes", exact: true }).click();
  await page
    .getByLabel("Add a note", { exact: true })
    .fill("Browser-tested customer context");
  await page.getByRole("button", { name: "Add note", exact: true }).click();
  await expect(
    page
      .locator(".note-card")
      .filter({ hasText: "Browser-tested customer context" }),
  ).toBeVisible();
  await page.screenshot({
    path: screenshots + "/lead-detail-1440.png",
    fullPage: true,
  });
  await page
    .getByRole("navigation", { name: "Work areas", exact: true })
    .getByRole("link", { name: "Home", exact: true })
    .click();
  await page
    .getByRole("navigation", { name: "Section navigation", exact: true })
    .getByRole("link", { name: "Planner", exact: true })
    .click();
  await page.getByRole("button", { name: "Create task", exact: true }).click();
  await page
    .getByLabel("Task title")
    .fill("Browser verified next step " + name);
  await page
    .getByLabel("Owner", { exact: true })
    .selectOption({ label: "Aarav Mehta" });
  await page.getByLabel("Due date & time").fill("2026-10-30T10:00");
  await page.getByRole("button", { name: "Save task" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("button", {
      name: "Complete Browser verified next step " + name,
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Complete Browser verified next step " + name,
      exact: true,
    }),
  ).toHaveCount(0);
});
test("CSV preview, partial errors, persisted import and idempotent retry", async ({
  page,
}) => {
  await login(page);
  await page.goto("/app/leads");
  await page.getByRole("button", { name: "Import leads" }).click();
  const n = String(Date.now()).slice(-7);
  const buffer = Buffer.from(
    `name,phone,city\nUI Import ${n},+91989${n},Pune\nInvalid phone,bad,Delhi\n`,
  );
  await page
    .getByLabel("Lead import file")
    .setInputFiles({ name: "ui-import.csv", mimeType: "text/csv", buffer });
  await page.getByRole("button", { name: "Validate & preview" }).click();
  await expect(
    page.getByRole("button", { name: "Import 1 valid leads" }),
  ).toBeVisible();
  await expect(page.locator(".import-errors")).toContainText("Row 3");
  await page.getByRole("button", { name: "Import 1 valid leads" }).click();
  await expect(page.locator(".import-counts")).toContainText("imported");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByLabel("Search lead list").fill("UI Import " + n);
  await expect(
    page.getByRole("link", { name: new RegExp("UI Import " + n) }).first(),
  ).toBeVisible();
});
test("telecaller permissions and optional-history failure remain usable", async ({
  page,
}) => {
  await login(page, "+919900000004");
  await expect(
    page.getByRole("link", { name: "Payroll estimates", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Workspace profile", exact: true }),
  ).toHaveCount(0);
  await page.goto("/app/leads");
  const first = page.locator("tbody .name-cell").first();
  await page.route("**/api/leads/*/history*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unavailable",
          message: "History temporarily unavailable",
        },
      }),
    }),
  );
  await first.click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(
    page.getByText("History temporarily unavailable", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Edit details", exact: true }),
  ).toBeVisible();
  await page.goto("/app/payroll");
  await expect(
    page.getByText("This workspace needs a different role"),
  ).toBeVisible();
});
test("location permission denial gives a retryable explanation", async ({
  page,
}) => {
  await login(page, "+919900000004");
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "geolocation", {
      value: {
        getCurrentPosition: (
          _ok: unknown,
          error: (e: { code: number }) => void,
        ) => error({ code: 1 }),
      },
    });
  });
  // Configure a local test geofence through a separate admin request; never changes real deployments.
  const r = await page.request.post("/api/auth/login", {
    data: { phone: "+919900000002", password: "LocalCRM!2026" },
  });
  const token = (await r.json()).access_token;
  await page.request.put("/api/settings", {
    headers: { Authorization: "Bearer " + token },
    data: {
      weekdays: [0, 1, 2, 3, 4],
      daily_hours: "8",
      workplace: {
        name: "Test Office",
        latitude: 19.076,
        longitude: 72.8777,
        accuracy: 0,
        radius: 200,
        timezone: "Asia/Kolkata",
      },
    },
  });
  await page.goto("/app/attendance");
  await page.getByRole("button", { name: "Check in", exact: true }).click();
  await expect(
    page.getByText("Location permission was denied.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Check in", exact: true }),
  ).toBeEnabled();
});
test("responsive pages stay within viewport at 360, 768 and 1440 pixels", async ({
  page,
}) => {
  for (const width of [360, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.locator("#contact")).toContainText(
      "Contact details are being configured",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `${screenshots}/public-${width}.png`,
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await login(page);
  for (const width of [360, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of [
      "overview",
      "leads",
      "attendance",
      "payroll",
      "settings",
    ]) {
      await page.goto("/app/" + route);
      await expect(page.locator(".skeletons")).toHaveCount(0);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBeTruthy();
      if (route === "leads" && width === 360) {
        const readable = await page
          .locator(".lead-toolbar > select")
          .evaluateAll((selects) =>
            selects.every((node) => {
              const select = node as HTMLSelectElement;
              const style = getComputedStyle(select);
              const canvas = document.createElement("canvas");
              const context = canvas.getContext("2d")!;
              context.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
              const available =
                select.clientWidth -
                parseFloat(style.paddingLeft) -
                parseFloat(style.paddingRight) -
                4;
              return (
                context.measureText(select.selectedOptions[0].text).width <=
                available
              );
            }),
          );
        expect(
          readable,
          "Status and source labels must fit on a narrow screen",
        ).toBeTruthy();
      }
      await page.screenshot({
        path: `${screenshots}/${route}-${width}.png`,
        fullPage: true,
      });
    }
  }
});
test("platform owner creates isolated organization and exits audited support", async ({
  page,
}) => {
  await login(page, "+919900000001");
  await page
    .getByRole("button", { name: "Create company", exact: true })
    .click();
  const name = "Browser organization " + Date.now();
  await page.getByLabel("Company name", { exact: true }).fill(name);
  await page.getByLabel("First administrator").fill("Browser Admin");
  await page
    .getByLabel("Administrator login phone")
    .fill("+9197" + String(Date.now()).slice(-8));
  await page
    .getByLabel("Initial administrator password")
    .fill("BrowserAdmin!123");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Create company", exact: true })
    .click();
  await expect(page.getByRole("dialog", { name, exact: true })).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const row = page
    .getByRole("row")
    .filter({ has: page.getByRole("button", { name, exact: true }) });
  await row.getByRole("button", { name: "Manage", exact: true }).click();
  await page
    .getByRole("button", { name: "Enter audited support workspace" })
    .click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await expect(page.locator(".support-banner")).toContainText(name);
  await expect(page.locator(".stat").first()).toContainText("0");
  await page.getByRole("button", { name: "Exit support", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/platform/);
  await expect(
    page.getByRole("heading", { name: "One platform. Independent companies." }),
  ).toBeVisible();
});
test("keyboard dialog behavior and accessibility audit on core pages", async ({
  page,
}) => {
  await page.goto("/");
  const publicResults = await new AxeBuilder({ page }).analyze();
  expect(
    publicResults.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  await page.goto("/login");
  const loginResults = await new AxeBuilder({ page }).analyze();
  expect(
    loginResults.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  await page.screenshot({
    path: screenshots + "/login-1440.png",
    fullPage: true,
  });
  await login(page);
  for (const route of [
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
  ]) {
    await page.goto("/app/" + route);
    await expect(page.locator(".skeletons")).toHaveCount(0);
    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact || ""),
      ),
      route,
    ).toEqual([]);
  }
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("employee time, administrator review and decimal payroll form a persisted browser journey", async ({
  page,
}) => {
  await login(page);
  await page.goto("/app/team");
  const name = "Time Journey " + Date.now();
  const phone = "+9196" + String(Date.now()).slice(-8);
  const password = "BrowserTime!123";
  await page.getByRole("button", { name: "Add team member" }).click();
  await page.getByLabel("Full name", { exact: true }).fill(name);
  await page.getByLabel("Login phone", { exact: true }).fill(phone);
  await page.getByLabel("Initial password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("row").filter({ hasText: name })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
  await login(page, phone, password);
  await page.goto("/app/approvals");
  await page.getByRole("button", { name: "Submit time", exact: true }).click();
  await page.getByLabel("Hours", { exact: true }).fill("2.5");
  await page
    .getByLabel("What did you work on?", { exact: true })
    .fill("Verified browser calling work");
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("row").filter({ hasText: "Verified browser calling work" }),
  ).toContainText("pending");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
  await login(page);
  await page.goto("/app/approvals");
  await page
    .getByRole("row")
    .filter({ hasText: name })
    .getByRole("button", { name: "Review", exact: true })
    .click();
  await page.getByLabel("Decision", { exact: true }).selectOption("approved");
  await page.getByRole("button", { name: "Record decision" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("row").filter({ hasText: name })).toContainText(
    "approved",
  );
  await page.goto("/app/payroll");
  const row = page.getByRole("row").filter({ hasText: name });
  await row.getByRole("button", { name: "Edit rate" }).click();
  await page.getByLabel("Hourly rate (₹)", { exact: true }).fill("125.25");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(row).toContainText("₹313.13");
  await page.screenshot({
    path: screenshots + "/payroll-verified-1440.png",
    fullPage: true,
  });
});

test("saved lead views, saved analytics reports and background automations work from browser controls", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  const label = "New leads";
  await page.goto("/app/leads");
  await page.getByLabel("Lead status", { exact: true }).selectOption("new");
  await page
    .getByRole("button", { name: "+ Save filters", exact: true })
    .click();
  await page.getByLabel("Filter name", { exact: true }).fill(label);
  await page.getByRole("button", { name: "Save filters", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: label, exact: true }),
  ).toBeVisible();
  await page.goto("/app/reports");
  await page
    .getByRole("button", { name: "+ Save current report", exact: true })
    .click();
  await page.getByLabel("Report name", { exact: true }).fill(label);
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: label, exact: true }),
  ).toBeVisible();
  await page.goto("/app/automations");
  await page.getByRole("button", { name: "Create rule", exact: true }).click();
  await page.getByLabel("Rule name", { exact: true }).fill(label);
  await page
    .getByLabel("Take this action", { exact: true })
    .selectOption("add_note");
  await page
    .getByLabel("Note text", { exact: true })
    .fill("A browser-configured automation ran");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  await page.getByLabel("Customer / buyer name", { exact: true }).fill(label);
  await page
    .getByLabel("Phone number", { exact: true })
    .fill("+9195" + String(Date.now()).slice(-8));
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("link", { name: new RegExp(label) })
    .first()
    .click();
  await page.getByRole("button", { name: "Notes", exact: true }).click();
  await expect(async () => {
    await page.getByRole("button", { name: "Activity", exact: true }).click();
    await page.getByRole("button", { name: "Notes", exact: true }).click();
    await expect(
      page
        .getByText("A browser-configured automation ran", { exact: true })
        .first(),
    ).toBeVisible();
  }).toPass({ timeout: 20000, intervals: [2000, 3000] });
  await page.goto("/app/automations");
  const card = page
    .locator(".automation-card")
    .filter({ has: page.getByRole("heading", { name: label, exact: true }) });
  await card.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(card).toContainText("paused");
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: `Remove saved filter ${label}`, exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: label, exact: true }),
  ).toHaveCount(0);
  await page.goto("/app/reports");
  await page
    .getByRole("button", { name: `Remove report ${label}`, exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: label, exact: true }),
  ).toHaveCount(0);
  expect(
    await workspace.api
      .get("/api/saved-views")
      .then((response) => response.json()),
  ).toEqual([]);
  await page.goto("/app/tasks");
  await page.getByRole("button", { name: "Calendar", exact: true }).click();
  await page.getByLabel("Calendar month").fill("");
  await expect(
    page.getByRole("heading", { name: "Tasks & calendar", exact: true }),
  ).toBeVisible();
});

test("saved filters use clear names, reapply after reload and remove without deleting leads", async ({
  page,
  workspace,
}) => {
  for (const [name, phone, source] of [
    ["Website enquiry", "+919800001001", "website"],
    ["Manual enquiry", "+919800001002", "manual"],
  ]) {
    const created = await workspace.api.post("/api/leads", {
      data: { name, phone, source },
    });
    expect(created.status(), await created.text()).toBe(201);
  }
  const other = await workspace.api.post("/api/saved-views", {
    data: { name: "New leads", kind: "leads", filters: { status: "new" } },
  });
  expect(other.status()).toBe(201);
  await login(page, workspace.phone);
  await page.goto("/app/leads");
  await expect(page.locator(".saved-views")).toContainText("Saved filters");
  await expect(page.locator(".saved-views")).not.toContainText("Browser view");
  await page.getByLabel("Lead source", { exact: true }).selectOption("website");
  await page
    .getByRole("button", { name: "+ Save filters", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Choose a clear name");
  await page
    .getByLabel("Filter name", { exact: true })
    .fill("Website enquiries");
  await page.getByRole("button", { name: "Save filters", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Website enquiries", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Lead source", { exact: true }).selectOption("");
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Website enquiries", exact: true })
    .click();
  await expect(page.getByLabel("Lead source", { exact: true })).toHaveValue(
    "website",
  );
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", {
      name: "Remove saved filter Website enquiries",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", { name: "Website enquiries", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "New leads", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Website enquiries", exact: true }),
  ).toHaveCount(0);
  const leads = await workspace.api
    .get("/api/leads")
    .then((response) => response.json());
  expect(leads.total).toBe(2);
  await page
    .getByRole("button", { name: "Remove saved filter New leads", exact: true })
    .click();
  await expect(page.locator(".view-chip")).toHaveCount(0);
  expect(
    await workspace.api
      .get("/api/saved-views")
      .then((response) => response.json()),
  ).toEqual([]);
  await page.screenshot({
    path: screenshots + "/saved-filters-clean.png",
    fullPage: true,
  });
});

test("failed sign-out remains visible and retry signs out successfully", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/auth/logout", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: {
          code: "unavailable",
          message: "Sign-out service temporarily unavailable",
        },
      }),
    }),
  );
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByText("Sign-out service temporarily unavailable", { exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.unroute("**/api/auth/logout");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("work areas expose every permitted destination and select context for deep links", async ({
  page,
}) => {
  const cases = [
    {
      phone: "+919900000002",
      studio: [
        "Workflows",
        "Connections",
        "Audit log",
        "Data snapshots",
        "Workspace profile",
        "Subscription",
        "Account & security",
      ],
      people: [
        "Attendance",
        "Requests & approvals",
        "Team directory",
        "Payroll estimates",
      ],
      sales: ["Leads", "Closed opportunities"],
    },
    {
      phone: "+919900000003",
      studio: ["Workflows", "Connections", "Audit log", "Account & security"],
      people: ["Attendance", "Requests & approvals", "Team directory"],
      sales: ["Leads", "Closed opportunities"],
    },
    {
      phone: "+919900000004",
      studio: ["Account & security"],
      people: ["Attendance", "Requests & approvals"],
      sales: ["Leads"],
    },
  ];
  for (const fixture of cases) {
    await login(page, fixture.phone);
    const areas = page.getByRole("navigation", {
      name: "Work areas",
      exact: true,
    });
    const section = page.getByRole("navigation", {
      name: "Section navigation",
      exact: true,
    });
    await expect(areas.getByRole("link")).toHaveText([
      "Home",
      "Sales",
      "Property",
      "People",
      "Insights",
      "Studio",
    ]);
    for (const [area, labels] of [
      ["Home", ["Overview", "Planner", "Conversations"]],
      ["Sales", fixture.sales],
      [
        "Property",
        fixture.phone === "+919900000004"
          ? ["Inventory", "Site visits"]
          : ["Inventory", "Site visits", "Bookings"],
      ],
      ["People", fixture.people],
      ["Insights", ["Reports"]],
      ["Studio", fixture.studio],
    ] as const) {
      await areas.getByRole("link", { name: area, exact: true }).click();
      await expect(section.getByRole("link")).toHaveText([...labels]);
      for (const label of labels) {
        await section.getByRole("link", { name: label, exact: true }).click();
        await expect(
          section.getByRole("link", { name: label, exact: true }),
        ).toHaveAttribute("aria-current", "page");
        await expect(page.locator(".skeletons")).toHaveCount(0);
        await expect(
          page.getByText("This workspace needs a different role", {
            exact: true,
          }),
        ).toHaveCount(0);
        await expect(page.locator("#workspace-main h1")).toBeVisible();
      }
    }
    await page.goto("/app/leads");
    await page.locator("tbody .name-cell").first().click();
    await page.reload();
    await expect(
      areas.getByRole("link", { name: "Sales", exact: true }),
    ).toHaveAttribute("aria-current", "true");
    await expect(
      section.getByRole("link", { name: "Leads", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page).toHaveURL(/\/login/);
  }
});

test("mobile work areas support keyboard, dismissal, route changes and desktop resize", async ({
  page,
  browserName,
}) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await login(page);
  const toggle = page.getByRole("button", {
    name: "Open navigation",
    exact: true,
  });
  const areas = page.getByRole("navigation", {
    name: "Work areas",
    exact: true,
  });
  await expect(areas).toBeHidden();
  await toggle.click();
  await expect(
    areas.getByRole("link", { name: "Home", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(areas).toBeHidden();
  await expect(toggle).toBeFocused();
  await toggle.click();
  // macOS WebKit follows Safari's default: Option-Tab includes links.
  await page.keyboard.press(
    browserName === "webkit" && process.platform === "darwin"
      ? "Alt+Tab"
      : "Tab",
  );
  await expect(
    areas.getByRole("link", { name: "Sales", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/app\/leads$/);
  await expect(areas).toBeHidden();
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await expect(
    page
      .getByRole("navigation", { name: "Section navigation", exact: true })
      .getByRole("link", { name: "Leads", exact: true }),
  ).toBeVisible();
  await toggle.click();
  await page
    .getByRole("button", { name: "Close navigation", exact: true })
    .click({ position: { x: 330, y: 150 } });
  await expect(areas).toBeHidden();
  await toggle.click();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator(".app-body")).not.toHaveAttribute("inert");
  await expect(areas).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Close navigation", exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("Search leads", { exact: true }).fill("Northstar");
  await page.getByLabel("Search leads", { exact: true }).press("Enter");
  await expect(page).toHaveURL(/\/app\/leads\?q=Northstar/);
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/app/settings");
  await expect(
    page
      .getByRole("navigation", { name: "Section navigation", exact: true })
      .getByRole("link", { name: "Workspace profile", exact: true }),
  ).toBeInViewport();
  await page
    .getByRole("navigation", { name: "Section navigation", exact: true })
    .getByRole("link", { name: "Account & security", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/security/);
  await expect(
    page
      .getByRole("navigation", { name: "Section navigation", exact: true })
      .getByRole("link", { name: "Account & security", exact: true }),
  ).toBeInViewport();
});

test("long client branding remains readable and contained across breakpoints", async ({
  page,
}) => {
  const clientBrand = "Meridian International Customer Relations Workspace";
  await page.route("**/api/auth/me", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.organization.settings.brand_name = clientBrand;
    data.organization.name =
      "Meridian Global Distribution and Professional Services Group";
    await route.fulfill({ response, json: data });
  });
  await login(page);
  await expect(page.locator(".product-wordmark")).toContainText(clientBrand);
  await expect(page).toHaveTitle(clientBrand + " · Home");
  expect(
    await page
      .locator(".topbar")
      .evaluate((el) => el.getBoundingClientRect().height),
  ).toBeLessThan(100);
  for (const width of [320, 360, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBeTruthy();
    await expect(
      page.getByRole("button", { name: "Sign out", exact: true }),
    ).toBeVisible();
  }
  await page.unroute("**/api/auth/me");
});

test("standard lead interests persist, score once, survive editing and can be cleared from the score card", async ({
  page,
}) => {
  await login(page);
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  const name = "Interest journey " + Date.now();
  await page.getByLabel("Customer / buyer name").fill(name);
  await page
    .getByLabel("Phone number", { exact: true })
    .fill("+9193" + String(Date.now()).slice(-8));
  await page.getByLabel("City", { exact: true }).fill("Pune");
  await page
    .getByLabel("Property / project interests", { exact: true })
    .fill("CRM setup\nSupport\ncrm SETUP\n  ");
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("link", { name: new RegExp(name) })
    .first()
    .click();
  const scoreCard = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Lead score", exact: true }),
  });
  await expect(scoreCard.locator(".score-number")).toContainText("45");
  await expect(
    scoreCard
      .locator(".detail-list > div")
      .filter({ hasText: "Interests recorded" }),
  ).toContainText("+15");
  await expect(
    page.locator(".detail-list dd").filter({ hasText: "CRM setup, Support" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Edit details", exact: true }).click();
  await expect(
    page.getByLabel("Property / project interests", { exact: true }),
  ).toHaveValue("CRM setup\nSupport");
  await page.getByLabel("City", { exact: true }).fill("Mumbai");
  await page.getByRole("button", { name: "Save lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(scoreCard.locator(".score-number")).toContainText("45");
  await scoreCard
    .getByRole("button", { name: "Edit interests", exact: true })
    .click();
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  await page
    .getByLabel("Property / project interests", { exact: true })
    .fill("");
  await page
    .getByRole("button", { name: "Save interests", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(scoreCard.locator(".score-number")).toContainText("30");
  await expect(
    scoreCard
      .locator(".detail-list > div")
      .filter({ hasText: "Interests recorded" }),
  ).toContainText("+0");
  await page.reload();
  await scoreCard
    .getByRole("button", { name: "Add interests", exact: true })
    .click();
  await expect(
    page.getByLabel("Property / project interests", { exact: true }),
  ).toHaveValue("");
  await page
    .getByLabel("Property / project interests", { exact: true })
    .fill(Array.from({ length: 31 }, (_, i) => "Product " + i).join("\n"));
  await page
    .getByRole("button", { name: "Save interests", exact: true })
    .click();
  await expect(page.getByRole("dialog").getByRole("alert")).toBeVisible();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(scoreCard.locator(".score-number")).toContainText("30");
  await page
    .getByLabel("Property / project interests", { exact: true })
    .fill("Implementation support");
  await page
    .getByRole("button", { name: "Save interests", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(scoreCard.locator(".score-number")).toContainText("45");
  await page.setViewportSize({ width: 360, height: 800 });
  await scoreCard
    .getByRole("button", { name: "Edit interests", exact: true })
    .click();
  await expect(
    page.getByLabel("Property / project interests", { exact: true }),
  ).toHaveValue("Implementation support");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: screenshots + "/mobile-editor.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("interest entry is available in both standard and pharma lead forms", async ({
  page,
}) => {
  await login(page);
  const auth = await page.request.post("/api/auth/login", {
    data: { phone: "+919900000002", password: "LocalCRM!2026" },
  });
  const headers = {
    Authorization: "Bearer " + (await auth.json()).access_token,
  };
  const before = (
    await (await page.request.get("/api/settings", { headers })).json()
  ).settings;
  const original = Object.fromEntries(
    ["weekdays", "daily_hours", "workplace", "brand_name", "pharma_enabled"]
      .filter((key) => key in before)
      .map((key) => [key, before[key]]),
  );
  try {
    for (const pharma of [false, true]) {
      const response = await page.request.put("/api/settings", {
        headers,
        data: { ...original, pharma_enabled: pharma },
      });
      expect(response.ok()).toBeTruthy();
      await page.goto("/app/leads");
      await page
        .getByRole("button", { name: "Add a lead", exact: true })
        .first()
        .click();
      await expect(
        page.getByLabel("Property / project interests", { exact: true }),
      ).toHaveCount(1);
      await expect(
        page.getByLabel("Primary category", { exact: true }),
      ).toHaveCount(pharma ? 1 : 0);
      await page
        .getByLabel("Customer / buyer name")
        .fill("Interest mode " + pharma + " " + Date.now());
      await page
        .getByLabel("Phone number", { exact: true })
        .fill("+9192" + String(Date.now()).slice(-8));
      await page
        .getByLabel("Property / project interests", { exact: true })
        .fill("Software implementation\nTeam training");
      await page
        .getByRole("button", { name: "Create lead", exact: true })
        .click();
      await expect(page.getByRole("dialog")).toHaveCount(0);
    }
  } finally {
    const response = await page.request.put("/api/settings", {
      headers,
      data: original,
    });
    expect(response.ok()).toBeTruthy();
  }
});

test("caller can record confirmed interests on their own lead using the score card", async ({
  page,
}) => {
  await login(page, "+919900000004");
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  const name = "Caller interests " + Date.now();
  await page.getByLabel("Customer / buyer name").fill(name);
  await page
    .getByLabel("Phone number", { exact: true })
    .fill("+9191" + String(Date.now()).slice(-8));
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("link", { name: new RegExp(name) })
    .first()
    .click();
  const scoreCard = page.locator(".panel").filter({
    has: page.getByRole("heading", { name: "Lead score", exact: true }),
  });
  await expect(scoreCard.locator(".score-number")).toContainText("20");
  await scoreCard
    .getByRole("button", { name: "Add interests", exact: true })
    .click();
  await page
    .getByLabel("Property / project interests", { exact: true })
    .fill("Onboarding assistance");
  await page
    .getByRole("button", { name: "Save interests", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(scoreCard.locator(".score-number")).toContainText("35");
  await page.reload();
  await expect(
    page
      .locator(".detail-list dd")
      .filter({ hasText: "Onboarding assistance" }),
  ).toBeVisible();
});
