import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { test, type Workspace } from "./fixtures";
import { randomInt, createHmac } from "node:crypto";
const password = "LocalCRM!2026";
const phone = () => "+9197" + String(randomInt(10000000, 99999999));
async function login(page: Page, number: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(number);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await expect(page.getByLabel("Sign out")).toBeVisible();
}
async function lead(
  workspace: Workspace,
  name = "QA customer",
  extra: Record<string, unknown> = {},
) {
  const response = await workspace.api.post("/api/leads", {
    data: { name, phone: phone(), ...extra },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}
const error = (message: string) => ({
  status: 503,
  contentType: "application/json",
  body: JSON.stringify({ error: { code: "unavailable", message } }),
});

test("delayed custom definitions retain required false, number, date and select values after reload", async ({
  page,
  workspace,
}) => {
  for (const [key, type, more] of [
    ["consent", "boolean", {}],
    ["units", "number", {}],
    ["requested", "date", {}],
    ["package", "select", { options: ["Basic", "Premium"] }],
  ] as const) {
    const response = await workspace.api.post("/api/definitions", {
      data: {
        kind: "field",
        key,
        label: "QA " + key,
        config: { type, required: true, ...more },
      },
    });
    expect(response.status()).toBe(201);
  }
  await login(page, workspace.phone);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route("**/api/definitions", async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Create lead" }),
  ).toBeDisabled();
  release();
  await page.getByLabel("Customer / buyer name").fill("Required false saved");
  await page
    .getByRole("dialog")
    .getByLabel("Phone number", { exact: false })
    .fill(phone());
  await expect(page.getByLabel("QA consent")).not.toBeChecked();
  await page.getByLabel("QA units").fill("0.25");
  await page.getByLabel("QA requested").fill("2026-10-30");
  await page.getByLabel("QA package").selectOption("Premium");
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const stored = (await (await workspace.api.get("/api/leads")).json())
    .items[0];
  expect(stored.custom).toEqual({
    consent: false,
    units: 0.25,
    requested: "2026-10-30",
    package: "Premium",
  });
  const definition = (
    await (await workspace.api.get("/api/definitions")).json()
  ).find((item: { key: string }) => item.key === "package");
  expect(
    (
      await workspace.api.put("/api/definitions/" + definition.id, {
        data: {
          kind: "field",
          key: "package",
          label: "QA package",
          config: { type: "select", required: true, options: ["Enterprise"] },
        },
      })
    ).ok(),
  ).toBeTruthy();
  await page.goto("/app/leads/" + stored.id);
  await page.getByRole("button", { name: "Edit details" }).click();
  await expect(page.getByLabel("QA consent")).not.toBeChecked();
  await expect(page.getByLabel("QA units")).toHaveValue("0.25");
  await expect(page.getByLabel("QA requested")).toHaveValue("2026-10-30");
  await expect(page.getByLabel("QA package")).toHaveValue("Premium");
  await expect(
    page
      .getByLabel("QA package")
      .getByRole("option", { name: "Premium (previous value)" }),
  ).toHaveCount(1);
  await page.getByLabel("City", { exact: true }).fill("Pune");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save lead" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const saved = await (
    await workspace.api.get("/api/leads/" + stored.id)
  ).json();
  expect(saved.city).toBe("Pune");
  expect(saved.custom.package).toBe("Premium");
});

test("failed definitions are visible, block incomplete submission and retry in the same dialog", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  await page.route("**/api/definitions", (route) =>
    route.fulfill(error("Definitions temporarily unavailable")),
  );
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Definitions temporarily unavailable",
  );
  await expect(
    page.getByRole("button", { name: "Create lead", exact: true }),
  ).toBeDisabled();
  await page.unroute("**/api/definitions");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Try again" })
    .click();
  await expect(page.getByLabel("Customer / buyer name")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create lead", exact: true }),
  ).toBeEnabled();
});

test("Escape during a delayed failed save preserves the form and supports a persisted retry", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  await page.goto("/app/leads");
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  await page.getByLabel("Customer / buyer name").fill("Interrupted save");
  await page
    .getByRole("dialog")
    .getByLabel("Phone number", { exact: false })
    .fill(phone());
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route("**/api/leads", async (route) => {
    if (route.request().method() === "POST") {
      await gate;
      await route.fulfill(error("Save unavailable. Retry your changes."));
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "Create lead" }),
  ).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeVisible();
  release();
  await expect(page.getByRole("dialog")).toContainText(
    "Save unavailable. Retry your changes.",
  );
  await expect(page.getByLabel("Customer / buyer name")).toHaveValue(
    "Interrupted save",
  );
  await page.unroute("**/api/leads");
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const result = await (await workspace.api.get("/api/leads")).json();
  expect(result.total).toBe(1);
  expect(result.items[0].name).toBe("Interrupted save");
});

test("searchable task selector reaches leads beyond 100 and preserves selection while editing", async ({
  page,
  workspace,
}) => {
  const old = await lead(workspace, "Older target");
  const csv =
    "name,phone\n" +
    Array.from({ length: 103 }, (_, i) => `Recent ${i},${phone()}`).join("\n");
  const imported = await workspace.api.post("/api/imports?commit=true", {
    multipart: {
      file: {
        name: "large.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(csv),
      },
    },
  });
  expect(imported.ok(), await imported.text()).toBeTruthy();
  expect((await imported.json()).imported).toBe(103);
  await login(page, workspace.phone);
  await page.goto("/app/tasks");
  await page.getByRole("button", { name: "Create task", exact: true }).click();
  await page.getByLabel("Task title").fill("Older lead follow-up");
  await page.getByLabel("Search related lead").fill("Older target");
  await expect(
    page
      .getByLabel("Related lead", { exact: true })
      .getByRole("option", { name: /Older target/ }),
  ).toHaveCount(1);
  await page.getByLabel("Related lead", { exact: true }).selectOption(old.id);
  await page.getByLabel("Owner", { exact: true }).selectOption(workspace.user);
  await page.getByLabel("Due date & time").fill("2026-10-30T10:00");
  await page.getByRole("button", { name: "Save task" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await page
    .getByRole("button", { name: "Older lead follow-up", exact: true })
    .click();
  await expect(page.getByLabel("Related lead", { exact: true })).toHaveValue(
    old.id,
  );
  await page.getByLabel("Search related lead").fill("No matching customer");
  await expect(
    page
      .getByLabel("Related lead", { exact: true })
      .getByRole("option", { name: /Older target/ }),
  ).toHaveCount(1);
  await expect(page.getByLabel("Related lead", { exact: true })).toHaveValue(
    old.id,
  );
  expect(
    (await (await workspace.api.get("/api/tasks")).json())[0].lead_id,
  ).toBe(old.id);
});

test("calendar resets a paginated task list and month changes retain the matching task", async ({
  page,
  workspace,
}) => {
  test.setTimeout(90000);
  const now = new Date();
  const month = now.toISOString().slice(0, 7);
  const old = new Date(
    now.getFullYear(),
    now.getMonth() - 1,
    10,
    10,
  ).toISOString();
  for (let i = 0; i < 101; i++) {
    const response = await workspace.api.post("/api/tasks", {
      data: {
        title: i === 100 ? "Current calendar task" : "Old task " + i,
        due_at: i === 100 ? month + "-15T10:00:00Z" : old,
        owner_id: workspace.user,
      },
    });
    expect(response.status()).toBe(201);
  }
  await login(page, workspace.phone);
  await page.goto("/app/tasks");
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.locator(".pagination")).toContainText("Page 2");
  await page.getByRole("button", { name: "Calendar", exact: true }).click();
  await expect(page.locator(".pagination")).toContainText("Page 1");
  await expect(
    page.getByRole("button", { name: /Current calendar task/ }),
  ).toBeVisible();
  await page.getByLabel("Calendar month").fill("2026-01");
  await expect(
    page.getByRole("button", { name: /Current calendar task/ }),
  ).toHaveCount(0);
  await page.getByLabel("Calendar month").fill(month);
  await expect(
    page.getByRole("button", { name: /Current calendar task/ }),
  ).toBeVisible();
});

test("saved date, stage and product filters display applied values, export correctly and clear hidden selection", async ({
  page,
  workspace,
}) => {
  const wanted = await lead(workspace, "Saved filter match", {
    interests: ["CRM Support"],
  });
  await lead(workspace, "Outside interest", { interests: ["Other"] });
  await login(page, workspace.phone);
  const from = new Date(Date.now() - 86400000).toISOString(),
    to = new Date(Date.now() + 86400000).toISOString();
  await page.goto(
    "/app/leads?" +
      new URLSearchParams({
        interest: "support",
        stage: "new",
        from_date: from,
        to_date: to,
      }),
  );
  await page.getByRole("button", { name: /^More filters/ }).click();
  await expect(
    page.getByLabel("Added from (time)", { exact: true }),
  ).not.toHaveValue("");
  await expect(
    page.getByLabel("Added before (time)", { exact: true }),
  ).not.toHaveValue("");
  await expect(page.getByLabel("Sales stage", { exact: true })).toHaveValue(
    "new",
  );
  await expect(
    page.getByLabel("Property / project interest", { exact: true }),
  ).toHaveValue("support");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await page
    .getByRole("button", { name: "+ Save filters", exact: true })
    .click();
  await page.getByLabel("Filter name").fill("Support this period");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save filters", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByLabel("Select " + wanted.name, { exact: true }).check();
  await expect(page.locator(".selection-bar")).toBeVisible();
  await page.getByRole("button", { name: /^All leads/ }).click();
  await expect(page.locator(".selection-bar")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Support this period", exact: true })
    .click();
  await page.reload();
  await page.getByRole("button", { name: /^More filters/ }).click();
  await expect(
    page.getByLabel("Property / project interest", { exact: true }),
  ).toHaveValue("support");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByLabel("Export filtered leads").click(),
  ]);
  const stream = await download.createReadStream();
  let body = "";
  for await (const chunk of stream!) body += chunk.toString();
  expect(body).toContain("Saved filter match");
  expect(body).not.toContain("Outside interest");
});

test("history older than a single page stays reachable and file download survives reload", async ({
  page,
  workspace,
}) => {
  const customer = await lead(workspace);
  for (let i = 0; i < 52; i++)
    expect(
      (
        await workspace.api.post(`/api/leads/${customer.id}/notes`, {
          data: { text: "History item " + i },
        })
      ).status(),
    ).toBe(201);
  await login(page, workspace.phone);
  await page.goto("/app/leads/" + customer.id);
  await page.getByRole("button", { name: "Notes", exact: true }).click();
  await expect(
    page.getByText("History item 51", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Older", exact: true }).click();
  await expect(page.getByText("History item 0", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Files", exact: true }).click();
  await expect(page.locator('[aria-label="History pagination"]')).toContainText(
    "Page 1",
  );
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGMUCTjBAAJMYJKBgQEAEkIBMLmziVsAAAAASUVORK5CYII=",
    "base64",
  );
  await page.locator("input[type=file]").setInputFiles({
    name: "Private QA.png",
    mimeType: "image/png",
    buffer: png,
  });
  await expect(page.getByText("Private QA.png", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Files", exact: true }).click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByLabel("Download Private QA.png", { exact: true }).click(),
  ]);
  const stream = await download.createReadStream();
  const chunks = [];
  for await (const chunk of stream!) chunks.push(chunk);
  expect(Buffer.concat(chunks)).toEqual(png);
});

test("temporary refresh failure keeps identity and recovers without login", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  await page.route("**/api/leads?*", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "token_expired", message: "Token expired" },
      }),
    }),
  );
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill(error("Session service temporarily unavailable")),
  );
  await page.goto("/app/leads");
  // Cold page reload also exercises the initial session restoration outage.
  await expect(
    page
      .getByText("Session service temporarily unavailable", { exact: true })
      .first(),
  ).toBeVisible();
  await expect(page).toHaveURL(/\/app\/leads/);
  await page.unroute("**/api/auth/refresh");
  await page.unroute("**/api/leads?*");
  await page.getByRole("button", { name: "Try again" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Your leads", exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Sign out")).toBeVisible();
});

test("expired access token refreshes once and a subsequent non-auth failure remains retryable", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  let calls = 0,
    refreshes = 0;
  await page.route("**/api/leads?*", async (route) => {
    calls++;
    if (refreshes === 0)
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: "{}",
      });
    else await route.fulfill(error("Lead service recovering"));
  });
  await page.route("**/api/auth/refresh", async (route) => {
    refreshes++;
    await route.continue();
  });
  await page
    .getByRole("navigation", { name: "Work areas", exact: true })
    .getByRole("link", { name: "Sales", exact: true })
    .click();
  await expect(
    page.getByText("Lead service recovering", { exact: true }),
  ).toBeVisible();
  expect(refreshes).toBe(1);
  expect(calls).toBeGreaterThanOrEqual(2);
  await expect(page.getByLabel("Sign out")).toBeVisible();
  await page.unroute("**/api/leads?*");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByText("Your next opportunity starts here", { exact: true }),
  ).toBeVisible();
});

function totp(secret: string) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of secret)
    bits += alphabet.indexOf(char).toString(2).padStart(5, "0");
  const key = Buffer.from(
    (bits.match(/.{8}/g) || []).map((byte) => parseInt(byte, 2)),
  );
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const hash = createHmac("sha1", key).update(counter).digest(),
    offset = hash[19] & 15;
  return String((hash.readUInt32BE(offset) & 0x7fffffff) % 1000000).padStart(
    6,
    "0",
  );
}
test("authenticator setup, invalid challenge, new-step login and disable persist through the UI", async ({
  page,
  workspace,
}) => {
  test.setTimeout(100000);
  await login(page, workspace.phone);
  await page.goto("/app/security");
  await page.getByRole("button", { name: "Set up authenticator" }).click();
  await page.getByLabel("Confirm your password").fill(password);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Generate setup key" })
    .click();
  const secret = (await page.locator(".setup-secret").textContent())!;
  await page
    .getByRole("button", { name: "I’ve added the account", exact: false })
    .click();
  await page.getByLabel("Current password").fill(password);
  const code = totp(secret);
  await page.getByLabel("Six-digit authenticator code").fill(code);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await expect(
    page.getByRole("button", { name: "Disable authenticator", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Sign out").click();
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Phone number").fill(workspace.phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await page
    .getByLabel("Authenticator code")
    .fill(String((Number(totp(secret)) + 1) % 1000000).padStart(6, "0"));
  await page.getByRole("button", { name: /Verify/ }).click();
  await expect(page.getByRole("alert")).toContainText(/incorrect|invalid/i);
  await expect
    .poll(() => totp(secret), { timeout: 35000, intervals: [250] })
    .not.toBe(code);
  await page.getByLabel("Authenticator code").fill(totp(secret));
  await page.getByRole("button", { name: /Verify/ }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await expect(page.getByLabel("Sign out")).toBeVisible();
  await page.goto("/app/security");
  await page
    .getByRole("button", { name: "Disable authenticator", exact: true })
    .click();
  await page.getByLabel("Current password").fill(password);
  await page.getByLabel("Six-digit authenticator code").fill(totp(secret));
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Set up authenticator" }),
  ).toBeVisible();
});

test("account changes clear previous organization data and revoked detail access stays denied", async ({
  page,
  workspace,
}) => {
  const customer = await lead(workspace, "Private previous organization");
  await workspace.api.post(`/api/leads/${customer.id}/notes`, {
    data: { text: "Private previous organization note" },
  });
  await login(page, workspace.phone);
  await page.goto("/app/leads/" + customer.id);
  await page.getByRole("button", { name: "Notes", exact: true }).click();
  await expect(
    page.getByText("Private previous organization note", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Sign out").click();
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Phone number").fill("+919900000006");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.goto("/app/leads/" + customer.id);
  await expect(page.getByRole("alert")).toContainText(/not found/i);
  await expect(
    page.getByText("Private previous organization note", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: "Private previous organization",
      exact: true,
    }),
  ).toHaveCount(0);
});

test("archiving the final row of a later lead page recovers to an existing page", async ({
  page,
  workspace,
}) => {
  const csv =
    "name,phone\n" +
    Array.from({ length: 26 }, (_, i) => `Page customer ${i},${phone()}`).join(
      "\n",
    );
  expect(
    (
      await workspace.api.post("/api/imports?commit=true", {
        multipart: {
          file: {
            name: "pages.csv",
            mimeType: "text/csv",
            buffer: Buffer.from(csv),
          },
        },
      })
    ).ok(),
  ).toBeTruthy();
  const last = (await (await workspace.api.get("/api/leads?page=2")).json())
    .items[0];
  await login(page, workspace.phone);
  await page.goto("/app/leads?page=2");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  expect(
    (
      await workspace.api.delete("/api/leads/" + last.id, {
        params: { confirmation: last.name },
      })
    ).ok(),
  ).toBeTruthy();
  await page.reload();
  await expect(page).toHaveURL(/page=1/);
  await expect(page.locator("tbody tr")).toHaveCount(25);
});

test("merge uses a required searchable duplicate and preserves customer context", async ({
  page,
  workspace,
}) => {
  const primary = await lead(workspace, "Primary customer", {
    interests: ["Support"],
  });
  const duplicate = await lead(workspace, "Duplicate customer", {
    interests: ["Implementation"],
  });
  expect(
    (
      await workspace.api.post(`/api/leads/${duplicate.id}/notes`, {
        data: { text: "Preserve duplicate context" },
      })
    ).status(),
  ).toBe(201);
  await login(page, workspace.phone);
  await page.goto("/app/leads/" + primary.id);
  await page
    .getByRole("button", { name: "Merge duplicate", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Merge records", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page
      .getByLabel("Duplicate lead", { exact: true })
      .evaluate((node: HTMLSelectElement) => node.validity.valueMissing),
  ).toBe(true);
  await page.getByLabel("Search duplicate lead").fill("Duplicate customer");
  await expect(
    page
      .getByLabel("Duplicate lead", { exact: true })
      .getByRole("option", { name: /Duplicate customer/ }),
  ).toHaveCount(1);
  await page
    .getByLabel("Duplicate lead", { exact: true })
    .selectOption(duplicate.id);
  await page
    .getByRole("button", { name: "Merge records", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("button", { name: "Notes", exact: true }).click();
  await expect(
    page.getByText("Preserve duplicate context", { exact: true }),
  ).toBeVisible();
  const saved = await (
    await workspace.api.get("/api/leads/" + primary.id)
  ).json();
  expect(saved.phone).toBe(primary.phone);
  expect(saved.interests).toEqual(["Support", "Implementation"]);
  expect((await workspace.api.get("/api/leads/" + duplicate.id)).status()).toBe(
    404,
  );
});

test("a valid sign-in clears an earlier bootstrap refresh outage", async ({
  page,
  workspace,
}) => {
  await page.route("**/api/auth/refresh", (route) =>
    route.fulfill(error("Refresh service recovering")),
  );
  await login(page, workspace.phone);
  await expect(
    page.getByRole("heading", {
      name: "Your real estate business, in focus.",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByLabel("Sign out")).toBeVisible();
});

test("directory failure is retryable inside task and automation forms", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  await page.route("**/api/directory", (route) =>
    route.fulfill(error("Team directory temporarily unavailable")),
  );
  await page.goto("/app/tasks");
  await page.getByRole("button", { name: "Create task", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Team directory temporarily unavailable",
  );
  await expect(
    page.getByRole("button", { name: "Save task", exact: true }),
  ).toBeDisabled();
  await page.unroute("**/api/directory");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Try again" })
    .click();
  await expect(
    page
      .getByRole("dialog")
      .getByLabel("Owner", { exact: true })
      .getByRole("option", { name: "QA Administrator" }),
  ).toHaveCount(1);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.route("**/api/directory", (route) =>
    route.fulfill(error("Team directory temporarily unavailable")),
  );
  await page.goto("/app/automations");
  await page
    .getByRole("button", { name: /Create.*rule|Create.*automation/ })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Team directory temporarily unavailable",
  );
  await page.unroute("**/api/directory");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Try again" })
    .click();
  await expect(page.getByLabel("Rule name")).toBeVisible();
});

test("loading states remain accessible while page and form requests are delayed", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  for (const path of ["**/api/definitions", "**/api/leads?*"])
    await page.route(path, async (route) => {
      await gate;
      await route.continue();
    });
  await page.goto("/app/leads");
  await expect(
    page.getByRole("status", { name: "Loading", exact: true }),
  ).toBeVisible();
  const loading = await new AxeBuilder({ page }).analyze();
  expect(
    loading.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact || ""),
    ),
  ).toEqual([]);
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("status", { name: "Loading form options", exact: true }),
  ).toBeVisible();
  const form = await new AxeBuilder({ page }).include(".dialog").analyze();
  expect(
    form.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact || ""),
    ),
  ).toEqual([]);
  release();
  await expect(page.getByLabel("Customer / buyer name")).toBeVisible();
});
