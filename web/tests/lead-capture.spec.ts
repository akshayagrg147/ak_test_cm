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
const number = () => "+9192" + randomInt(10000000, 99999999);
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/lead-capture") +
  "/screenshots";
mkdirSync(output, { recursive: true });

async function signedApi(phone: string) {
  const api = await request.newContext({
    baseURL,
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  const auth = await api.post("/api/auth/login", { data: { phone, password } });
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
async function company(owner: APIRequestContext) {
  const adminPhone = number(),
    name = "Capture Realty " + Date.now() + " " + randomInt(9999);
  const created = await owner.post("/api/platform/organizations", {
    data: {
      name,
      industry: "real_estate",
      admin: {
        name: "Capture Admin",
        phone: adminPhone,
        password,
        role: "admin",
      },
    },
  });
  expect(created.status(), await created.text()).toBe(201);
  const id = (await created.json()).organization.id as string;
  return { id, name, adminPhone };
}

test("admin turns on capture channels, a website lead arrives auto-assigned and alerts the team", async ({
  page,
  browser,
}) => {
  const owner = await signedApi("+919900000001");
  const org = await company(owner);
  const admin = await signedApi(org.adminPhone);
  const callerPhone = number();
  try {
    const caller = await admin.post("/api/team", {
      data: {
        name: "Capture Caller",
        phone: callerPhone,
        password,
        role: "telecaller",
      },
    });
    expect(caller.status(), await caller.text()).toBe(201);
    await login(page, org.adminPhone);
    const checklist = page.getByRole("region", {
      name: "Get your workspace ready",
    });
    await expect(checklist).toContainText("Start capturing enquiries (to do)");
    await checklist.getByRole("link", { name: "Set up lead capture" }).click();
    await expect(page).toHaveURL(/\/app\/integrations/);
    const panel = page.getByRole("region", { name: "Lead capture" });
    await expect(panel).toContainText("Round-robin across 1 active telecaller");
    await panel
      .getByRole("checkbox", { name: /Assign new enquiries automatically/ })
      .check();
    await expect(
      panel.getByRole("checkbox", {
        name: /Assign new enquiries automatically/,
      }),
    ).toBeChecked();
    await panel.getByRole("button", { name: "Turn on form" }).click();
    await expect(panel.getByText(/\/enquiry\//)).toBeVisible();
    const websiteCard = panel
      .locator(".capture-card")
      .filter({ hasText: "Website integration" });
    await websiteCard
      .getByRole("button", { name: "Turn on and get key" })
      .click();
    const keyBox = websiteCard.locator(".capture-key");
    await expect(keyBox).toContainText("won't be shown again");
    const key = (await keyBox.locator("code").textContent()) || "";
    expect(key.length).toBeGreaterThan(30);
    await checkAccessible(page);
    await page.screenshot({
      path: output + "/lead-capture-settings.png",
      fullPage: true,
    });

    const webhook = await request.newContext({ baseURL });
    const delivered = await webhook.post(`/api/capture/${org.id}/website`, {
      headers: { "X-Webhook-Token": key },
      data: {
        id: "browser-site-1",
        name: "Website Buyer",
        phone: "+919811177001",
        email: "buyer@example.com",
        budget: "90 lakh",
        message: "Looking for 3 BHK",
      },
    });
    expect(delivered.status(), await delivered.text()).toBe(200);
    await webhook.dispose();

    await page.reload();
    await expect(
      page.getByRole("region", { name: "Lead capture" }),
    ).toContainText("1 enquiry captured in the last 7 days");
    await expect(
      page.getByRole("row").filter({ hasText: "Website integration" }),
    ).toContainText("1");
    // The key is never shown again after reload.
    await expect(page.locator(".capture-key")).toHaveCount(0);

    const callerContext = await browser.newContext();
    const callerPage = await callerContext.newPage();
    await login(callerPage, callerPhone);
    await callerPage.getByRole("button", { name: /Notifications/ }).click();
    const alert = callerPage.getByRole("link", {
      name: /New enquiry — call now/,
    });
    await expect(alert).toContainText("Website Buyer");
    await alert.click();
    await expect(callerPage.getByText("Looking for 3 BHK")).toBeVisible();
    await expect(callerPage.getByText("Budget: 90 lakh")).toBeVisible();
    await callerContext.close();
  } finally {
    await admin.dispose();
    const removed = await owner.delete(
      "/api/platform/organizations/" + org.id,
      {
        params: { confirmation: org.name },
      },
    );
    expect(removed.ok()).toBeTruthy();
    await owner.dispose();
  }
});

test("a client sends an enquiry from the public form on a phone and the admin sees speed to lead", async ({
  page,
  browser,
}) => {
  const owner = await signedApi("+919900000001");
  const org = await company(owner);
  const admin = await signedApi(org.adminPhone);
  try {
    const settings = await admin.put("/api/lead-capture", {
      data: { form_enabled: true },
    });
    const formUrl = new URL((await settings.json()).form.url).pathname;
    const client = await browser.newContext({
      viewport: { width: 390, height: 844 },
    });
    const visitor = await client.newPage();
    await visitor.goto(baseURL + "/enquiry/not-a-real-form");
    await expect(
      visitor.getByRole("heading", { name: "This form isn't available" }),
    ).toBeVisible();
    await visitor.goto(baseURL + formUrl);
    await expect(
      visitor.getByRole("heading", { name: org.name }),
    ).toBeVisible();
    await visitor.getByLabel("Your name *").fill("Phone Visitor");
    await visitor.getByLabel("Mobile number *").fill("98111 77002");
    await visitor.getByLabel("I want to").selectOption("rent");
    await visitor.getByLabel("Budget").fill("35k per month");
    await visitor.getByLabel("Message").fill("2 BHK near metro");
    await checkAccessible(visitor);
    await visitor.screenshot({
      path: output + "/enquiry-form-mobile.png",
      fullPage: true,
    });
    await visitor.getByRole("button", { name: "Send enquiry" }).click();
    // Consent is required by the browser before sending.
    await expect(
      visitor.getByRole("heading", { name: "Thank you!" }),
    ).toHaveCount(0);
    await visitor
      .getByRole("checkbox", { name: /I agree to be contacted/ })
      .check();
    await visitor.getByRole("button", { name: "Send enquiry" }).click();
    await expect(
      visitor.getByRole("heading", { name: "Thank you!" }),
    ).toBeVisible();
    await expect(
      visitor.getByText(`${org.name} has your enquiry`),
    ).toBeVisible();
    await client.close();

    const leads = await (
      await admin.get("/api/leads?q=Phone%20Visitor")
    ).json();
    expect(leads.items[0].source).toBe("website");
    expect(leads.items[0].notes).toContain("Looking to: rent");
    expect(leads.items[0].enquiry_at).toBeTruthy();

    await login(page, org.adminPhone);
    const speed = page.getByRole("region", { name: "Speed to lead" });
    await expect(speed).toContainText("Still waiting for a call");
    await expect(speed).toContainText("No responses yet");
    await expect(speed.locator("dd.attention")).toHaveText("1");
    await checkAccessible(page);
  } finally {
    await admin.dispose();
    const removed = await owner.delete(
      "/api/platform/organizations/" + org.id,
      {
        params: { confirmation: org.name },
      },
    );
    expect(removed.ok()).toBeTruthy();
    await owner.dispose();
  }
});
