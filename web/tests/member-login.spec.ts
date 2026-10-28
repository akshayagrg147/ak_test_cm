import { randomInt } from "node:crypto";
import { mkdirSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { test, type Workspace } from "./fixtures";

const password = "LocalCRM!2026";
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/member-login") +
  "/screenshots";
mkdirSync(output, { recursive: true });

async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/(overview|platform)/);
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

test("administrator clicks member name, uses their real workspace and returns after reload", async ({
  page,
  workspace,
}) => {
  const caller = await member(workspace, "QA Direct Member");
  const own = await workspace.api.post("/api/leads", {
    data: { name: "QA member customer", phone: "+919876540451" },
  });
  const lead = await own.json();
  expect(
    (
      await workspace.api.post("/api/leads/assign", {
        data: { lead_ids: [lead.id], owner_id: caller.id },
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await workspace.api.post("/api/leads", {
        data: { name: "QA unassigned customer", phone: "+919876540452" },
      })
    ).ok(),
  ).toBeTruthy();
  await login(page, workspace.phone);
  await page.goto("/app/team");
  await page.getByRole("button", { name: caller.name, exact: true }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  const banner = page.getByRole("region", {
    name: "Member login",
    exact: true,
  });
  await expect(banner).toContainText("Signed in as QA Direct Member");
  await expect(banner).toContainText("Opened by QA Administrator");
  await page.reload();
  await expect(banner).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: "Account for QA Direct Member",
      exact: true,
    }),
  ).toBeVisible();
  await page.goto("/app/leads");
  await expect(
    page.getByRole("link", { name: new RegExp("QA member customer") }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: new RegExp("QA unassigned customer") }),
  ).toHaveCount(0);
  await page.goto("/app/leads/" + lead.id);
  await page.getByRole("button", { name: "Notes", exact: true }).click();
  await page
    .getByLabel("Add a note", { exact: true })
    .fill("QA saved from direct member login");
  await page.getByRole("button", { name: "Add note", exact: true }).click();
  await expect(
    page
      .locator(".note-card")
      .filter({ hasText: "QA saved from direct member login" }),
  ).toBeVisible();
  const history = await (
    await workspace.api.get("/api/leads/" + lead.id + "/history")
  ).json();
  expect(
    history.notes.some(
      (note: { author_id: string; text: string }) =>
        note.author_id === caller.id &&
        note.text === "QA saved from direct member login",
    ),
  ).toBeTruthy();
  await page.goto("/app/security");
  await expect(
    page.getByRole("button", { name: "Change password", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Set up authenticator", exact: true }),
  ).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(banner).toBeVisible();
  expect(
    await banner.evaluate(
      (element) => element.scrollWidth <= element.clientWidth + 1,
    ),
  ).toBeTruthy();
  await page.setViewportSize({ width: 320, height: 844 });
  expect(
    await banner
      .locator("strong")
      .evaluate((element) => element.getBoundingClientRect().width),
  ).toBeGreaterThan(200);
  const textBounds = await banner.locator("div").boundingBox();
  const buttonBounds = await banner
    .getByRole("button", { name: "Return to my account", exact: true })
    .boundingBox();
  expect(buttonBounds!.y).toBeGreaterThanOrEqual(
    textBounds!.y + textBounds!.height,
  );
  const axe = await new AxeBuilder({ page })
    .include(".member-login-banner")
    .analyze();
  expect(
    axe.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  await page.screenshot({
    path: output + "/member-account.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Return to my account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/team/);
  await expect(banner).toHaveCount(0);
  await expect(
    page.getByRole("link", {
      name: "Account for QA Administrator",
      exact: true,
    }),
  ).toBeVisible();
});

test("entry and return failures preserve identity and allow a successful retry", async ({
  page,
  workspace,
}) => {
  const caller = await member(workspace, "QA Retry Member");
  const inactive = await member(workspace, "QA Inactive Member");
  expect(
    (
      await workspace.api.patch("/api/team/" + inactive.id, {
        data: { active: false },
      })
    ).ok(),
  ).toBeTruthy();
  await login(page, workspace.phone);
  await page.goto("/app/team");
  await expect(
    page
      .getByRole("row")
      .filter({ hasText: inactive.name })
      .getByRole("button", { name: "Log in as member", exact: true }),
  ).toHaveCount(0);
  let failEntry = true;
  await page.route("**/api/team/" + caller.id + "/login-as", async (route) => {
    if (failEntry) {
      failEntry = false;
      await route.fulfill({
        status: 503,
        json: { error: { message: "Temporary member login failure" } },
      });
    } else await route.continue();
  });
  const action = page
    .getByRole("row")
    .filter({ hasText: caller.name })
    .getByRole("button", { name: "Log in as member", exact: true });
  await action.click();
  await expect(page.getByRole("alert")).toContainText(
    "Temporary member login failure",
  );
  await expect(
    page.getByRole("link", {
      name: "Account for QA Administrator",
      exact: true,
    }),
  ).toBeVisible();
  await action.click();
  const banner = page.getByRole("region", {
    name: "Member login",
    exact: true,
  });
  await expect(banner).toContainText(caller.name);
  let failExit = true;
  await page.route("**/api/auth/login-as/exit", async (route) => {
    if (failExit) {
      failExit = false;
      await route.fulfill({
        status: 503,
        json: { error: { message: "Temporary return failure" } },
      });
    } else await route.continue();
  });
  await banner
    .getByRole("button", { name: "Return to my account", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Temporary return failure",
  );
  await expect(banner).toContainText(caller.name);
  await banner
    .getByRole("button", { name: "Return to my account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/team/);
  await expect(banner).toHaveCount(0);
});

test("manager account has no login-as action and super admin can return through support", async ({
  page,
  workspace,
}) => {
  const manager = await member(workspace, "QA Login Manager", "manager");
  const caller = await member(workspace, "QA Support Member");
  await login(page, manager.phone);
  await page.goto("/app/team");
  await expect(
    page.getByRole("button", { name: "Log in as member", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: caller.name, exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "+919900000001");
  await page.getByLabel("Search companies").fill(workspace.name);
  await page
    .getByRole("row")
    .filter({ hasText: workspace.name })
    .getByRole("button", { name: "Manage", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Enter audited support workspace",
      exact: true,
    })
    .click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.goto("/app/team");
  await page.getByRole("button", { name: caller.name, exact: true }).click();
  await expect(
    page.getByRole("region", { name: "Member login", exact: true }),
  ).toContainText(caller.name);
  await page
    .getByRole("button", { name: "Return to my account", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/team/);
  await expect(
    page.getByRole("button", { name: "Exit support", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Exit support", exact: true }).click();
  await expect(page).toHaveURL(/\/app\/platform/);
});
