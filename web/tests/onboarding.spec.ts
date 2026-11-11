import { randomInt } from "node:crypto";
import { mkdirSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  request,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

const password = "LocalCRM!2026";
const baseURL = process.env.E2E_BASE_URL || "http://localhost:5173";
const number = () => "+9193" + randomInt(10000000, 99999999);
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/onboarding") + "/screenshots";
mkdirSync(output, { recursive: true });

async function signedApi(phone: string) {
  const api = await request.newContext({
    baseURL,
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  const auth = await api.post("/api/auth/login", {
    data: { phone, password },
  });
  expect(auth.ok(), await auth.text()).toBeTruthy();
  const token = (await auth.json()).access_token;
  await api.dispose();
  return request.newContext({
    baseURL,
    extraHTTPHeaders: {
      "X-Requested-With": "TalkoCRM",
      Authorization: "Bearer " + token,
    },
  });
}
async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/(platform|overview)/);
}
async function checkAccessible(page: Page) {
  const result = await new AxeBuilder({ page }).analyze();
  expect(
    result.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
}
async function createCompany(owner: APIRequestContext, trialDays: number) {
  const adminPhone = number(),
    name = "Onboarding Realty " + Date.now() + " " + randomInt(9999);
  const created = await owner.post("/api/platform/organizations", {
    data: {
      name,
      industry: "real_estate",
      profile: { city: "Pune" },
      trial_days: trialDays,
      admin: {
        name: "Setup Admin",
        phone: adminPhone,
        password,
        role: "admin",
      },
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  return {
    id: (await created.json()).organization.id as string,
    name,
    adminPhone,
  };
}
async function archive(
  owner: APIRequestContext,
  company: { id: string; name: string },
) {
  const removed = await owner.delete(
    "/api/platform/organizations/" + company.id,
    { params: { confirmation: company.name } },
  );
  expect(removed.ok(), await removed.text()).toBeTruthy();
}

test("new company admin sees a live setup checklist, trial countdown and an honest distribution hint", async ({
  page,
}) => {
  const owner = await signedApi("+919900000001");
  const company = await createCompany(owner, 1);
  try {
    await login(page, company.adminPhone);
    const checklist = page.getByRole("region", {
      name: "Get your workspace ready",
    });
    await expect(checklist).toBeVisible();
    await expect(checklist).toContainText("0 of 6 steps complete");
    await expect(checklist.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "0",
    );
    await expect(checklist).toContainText("Your trial ends today");
    await expect(checklist).toContainText(
      "1 of 9 details added. Missing: contact person, email",
    );
    await expect(checklist).toContainText("Add a telecaller (to do)");
    await expect(
      checklist.getByRole("link", { name: "Add team member" }),
    ).toHaveAttribute("href", "/app/team");
    await page.screenshot({
      path: output + "/setup-checklist.png",
      fullPage: true,
    });
    await checkAccessible(page);

    await page.getByRole("link", { name: "Sales" }).first().click();
    await expect(page).toHaveURL(/\/app\/leads/);
    await expect(
      page.getByText("No active telecallers to distribute leads to."),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Distribute unassigned" }),
    ).toHaveCount(0);
    await page.getByRole("link", { name: "Add a telecaller" }).click();
    await expect(page).toHaveURL(/\/app\/team/);

    const admin = await signedApi(company.adminPhone);
    const caller = await admin.post("/api/team", {
      data: {
        name: "First Caller",
        phone: number(),
        password,
        role: "telecaller",
      },
    });
    expect(caller.status(), await caller.text()).toBe(201);
    const lead = await admin.post("/api/leads", {
      data: { name: "Checklist Buyer", phone: number() },
    });
    expect(lead.status(), await lead.text()).toBe(201);
    await admin.dispose();

    await page.goto("/app/leads");
    await expect(
      page.getByRole("button", { name: "Distribute unassigned" }),
    ).toBeVisible();
    await expect(
      page.getByText("No active telecallers to distribute leads to."),
    ).toHaveCount(0);

    await page.goto("/app/overview");
    await expect(checklist).toContainText("2 of 6 steps complete");
    await expect(checklist).toContainText("Add a telecaller (done)");
    await expect(checklist).toContainText("1 active telecaller can receive");
    await expect(checklist).toContainText("Add or import leads (done)");

    await page.goto("/app/billing");
    await expect(page.getByText("Your trial ends today")).toBeVisible();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/app/overview");
    await expect(checklist).toBeVisible();
    await checkAccessible(page);
    await page.screenshot({
      path: output + "/setup-checklist-mobile.png",
      fullPage: true,
    });
  } finally {
    await archive(owner, company);
    await owner.dispose();
  }
});

test("super admin sees ending and expired subscriptions, profile progress, payment readiness and a 2FA prompt", async ({
  page,
}) => {
  const owner = await signedApi("+919900000001");
  const company = await createCompany(owner, 3);
  try {
    // Expired companies cannot be created through the API, so one row is shown expired in the response.
    await page.route("**/api/platform", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.organizations = [
        ...body.organizations,
        {
          ...body.organizations.find(
            (o: { id: string }) => o.id === company.id,
          ),
          id: "expired-example",
          name: "Lapsed Example Realty",
          subscription: {
            ...body.organizations.find(
              (o: { id: string }) => o.id === company.id,
            ).subscription,
            effective_status: "expired",
            days_left: -2,
          },
        },
      ];
      body.expired += 1;
      body.payments = {
        plans: 0,
        upi_ready: false,
        cod_ready: false,
        ready: false,
      };
      await route.fulfill({ response, json: body });
    });
    await login(page, "+919900000001");
    await expect(
      page.getByText("Protect your super admin account"),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Set up authenticator" }),
    ).toHaveAttribute("href", "/app/security");
    const attention = page.getByRole("status").filter({
      hasText: "within 7 days",
    });
    await expect(attention).toContainText("1 has expired");
    await expect(attention).toContainText(company.name + " · 2 days left");
    await expect(attention).toContainText("Lapsed Example Realty · Expired");
    await expect(page.getByText("Companies can't pay you yet")).toBeVisible();
    await expect(
      page.getByText(
        "publish at least one active subscription plan and upload your payment QR",
      ),
    ).toBeVisible();
    const row = page.getByRole("row").filter({ hasText: company.name });
    await expect(row).toContainText("Pune · Profile 1/9");
    await expect(row).toContainText("2 days left");
    await checkAccessible(page);
    await page.screenshot({
      path: output + "/super-admin-attention.png",
      fullPage: true,
    });

    await row.getByRole("button", { name: "Manage" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText(
      "Profile 1 of 9 complete · Missing: contact person, email, contact phone, state",
    );
    await expect(dialog).toContainText("2 days left");
    await dialog.getByRole("button", { name: "Close dialog" }).click();

    await page.route("**/api/platform/billing", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.plans = [];
      body.config = {
        ...body.config,
        upi_enabled: true,
        qr_ready: false,
        cod_enabled: false,
      };
      await route.fulfill({ response, json: body });
    });
    await page.goto("/app/platform/billing");
    await expect(page.getByText("Companies can't pay you yet")).toBeVisible();
    await expect(
      page.locator(".method-summary").filter({ hasText: "UPI / QR" }),
    ).toContainText("not ready");
    await expect(
      page.getByText("Upload your QR and payee name to accept UPI."),
    ).toBeVisible();
    await expect(
      page.locator(".method-summary").filter({ hasText: "Cash collection" }),
    ).toContainText("off");
    await checkAccessible(page);

    await page.unroute("**/api/platform/billing");
    await page.route("**/api/platform/billing", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.plans = [
        {
          id: "plan-example",
          name: "Example plan",
          description: "",
          monthly_price: "999.00",
          yearly_price: "9990.00",
          seats: 5,
          active: true,
        },
      ];
      body.config = { ...body.config, upi_enabled: false, cod_enabled: true };
      await route.fulfill({ response, json: body });
    });
    await page.reload();
    await expect(
      page.locator(".method-summary").filter({ hasText: "Cash collection" }),
    ).toContainText("ready");
    await expect(page.getByText("Companies can't pay you yet")).toHaveCount(0);
  } finally {
    await archive(owner, company);
    await owner.dispose();
  }
});
