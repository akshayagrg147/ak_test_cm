import { randomInt } from "node:crypto";
import { mkdirSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import { expect, request, type Page } from "@playwright/test";
import { test } from "./fixtures";

const password = "LocalCRM!2026";
const number = () => "+9194" + randomInt(10000000, 99999999);
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/super-admin-payments") +
  "/screenshots";
mkdirSync(output, { recursive: true });
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGMUCTjBAAJMYJKBgQEAEkIBMLmziVsAAAAASUVORK5CYII=",
  "base64",
);
async function ownerApi() {
  const api = await request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  const auth = await api.post("/api/auth/login", {
    data: { phone: "+919900000001", password },
  });
  expect(auth.ok()).toBeTruthy();
  const token = (await auth.json()).access_token;
  await api.dispose();
  return request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    extraHTTPHeaders: {
      "X-Requested-With": "TalkoCRM",
      Authorization: "Bearer " + token,
    },
  });
}
async function login(page: Page, phone = "+919900000001", value = password) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(value);
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

test("super admin creates company and first login, then changes and removes its logo", async ({
  page,
}) => {
  const owner = await ownerApi(),
    name = "QA Company Onboarding " + Date.now(),
    phone = number();
  let id = "";
  try {
    await login(page);
    await page
      .getByRole("button", { name: "Create company", exact: true })
      .click();
    await page.getByLabel("Company name", { exact: true }).fill(name);
    await page.getByLabel("Workspace brand name").fill("Panipat Homes QA");
    await page.getByLabel("Company city", { exact: true }).fill("Panipat");
    await page
      .getByLabel("First administrator", { exact: true })
      .fill("Onboarding Admin");
    await page
      .getByLabel("Administrator login phone", { exact: true })
      .fill(phone);
    await page.getByLabel("Initial administrator password").fill(password);
    await page
      .getByRole("dialog", {
        name: "Create a real estate company",
        exact: true,
      })
      .getByRole("button", { name: "Create company", exact: true })
      .click();
    const company = page.getByRole("dialog", { name, exact: true });
    await expect(company).toBeVisible();
    const listed = await (await owner.get("/api/platform")).json();
    id = listed.organizations.find((o: { name: string }) => o.name === name).id;
    await company.getByLabel("Upload company logo").setInputFiles({
      name: "first-logo.png",
      mimeType: "image/png",
      buffer: png,
    });
    await expect(
      company.getByRole("img", { name: "Company logo", exact: true }),
    ).toBeVisible();
    const firstLogo = (
      await (await owner.get(`/api/platform/organizations/${id}`)).json()
    ).organization.settings.logo_id;
    await company.getByLabel("Change company logo").setInputFiles({
      name: "bad-logo.png",
      mimeType: "image/png",
      buffer: Buffer.from("not an image"),
    });
    await expect(company.getByRole("alert")).toBeVisible();
    await expect(
      company.getByRole("img", { name: "Company logo", exact: true }),
    ).toBeVisible();
    await company.getByLabel("Change company logo").setInputFiles({
      name: "replacement.png",
      mimeType: "image/png",
      buffer: png,
    });
    await expect
      .poll(
        async () =>
          (await (await owner.get(`/api/platform/organizations/${id}`)).json())
            .organization.settings.logo_id,
      )
      .not.toBe(firstLogo);
    await company
      .getByRole("button", { name: "Remove company logo", exact: true })
      .click();
    await expect(company.getByLabel("Upload company logo")).toBeVisible();
    await expect(
      company.getByRole("img", { name: "Company logo", exact: true }),
    ).toHaveCount(0);
    await company.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await login(page, phone);
    await expect(page.locator(".product-name")).toContainText(
      "Panipat Homes QA",
    );
    await page.screenshot({
      path: output + "/new-company-admin.png",
      fullPage: true,
    });
  } finally {
    if (!id) {
      const d = await (await owner.get("/api/platform")).json();
      id =
        d.organizations.find((o: { name: string }) => o.name === name)?.id ||
        "";
    }
    if (id)
      expect(
        (
          await owner.delete(`/api/platform/organizations/${id}`, {
            params: { confirmation: name },
          })
        ).ok(),
      ).toBeTruthy();
    await owner.dispose();
  }
});

test("super admin adds and edits admins with duplicate retry, password reset and last-admin protection", async ({
  page,
  workspace,
}) => {
  await page.setViewportSize({ width: 390, height: 950 });
  await login(page);
  await page.getByLabel("Search companies").fill(workspace.name);
  await page
    .getByRole("row")
    .filter({ hasText: workspace.name })
    .getByRole("button", { name: "Manage", exact: true })
    .click();
  const company = page.getByRole("dialog", {
    name: workspace.name,
    exact: true,
  });
  await expect(
    company.getByRole("button", {
      name: "Deactivate administrator QA Administrator",
      exact: true,
    }),
  ).toBeDisabled();
  await company
    .getByRole("button", { name: "Add administrator", exact: true })
    .click();
  const add = page.getByRole("dialog", {
    name: "Add company administrator",
    exact: true,
  });
  await add.getByLabel("Administrator name").fill("Additional Admin QA");
  await add
    .getByLabel("Administrator login phone", { exact: true })
    .fill(workspace.phone);
  await add
    .getByLabel("Administrator password", { exact: true })
    .fill(password);
  await add
    .getByRole("button", { name: "Create administrator", exact: true })
    .click();
  await expect(add.getByRole("alert")).toContainText("already in use");
  const phone = number();
  await add
    .getByLabel("Administrator login phone", { exact: true })
    .fill(phone);
  await add
    .getByRole("button", { name: "Create administrator", exact: true })
    .click();
  await expect(add).toHaveCount(0);
  const row = company
    .getByRole("row")
    .filter({ hasText: "Additional Admin QA" });
  await expect(row).toContainText(phone);
  await row
    .getByRole("button", { name: "Edit administrator", exact: true })
    .click();
  const edit = page.getByRole("dialog", {
    name: "Edit company administrator",
    exact: true,
  });
  await edit.getByLabel("Administrator name").fill("Updated Admin QA");
  const newPassword = "ResetPassword!2026";
  await edit.getByLabel("New password (optional)").fill(newPassword);
  await edit
    .getByRole("button", { name: "Save administrator", exact: true })
    .click();
  await expect(edit).toHaveCount(0);
  const updated = company
    .getByRole("row")
    .filter({ hasText: "Updated Admin QA" });
  await updated
    .getByRole("button", {
      name: "Deactivate administrator Updated Admin QA",
      exact: true,
    })
    .click();
  await expect(updated).toContainText("inactive");
  await updated
    .getByRole("button", {
      name: "Reactivate administrator Updated Admin QA",
      exact: true,
    })
    .click();
  await expect(
    updated.getByRole("button", {
      name: "Deactivate administrator Updated Admin QA",
      exact: true,
    }),
  ).toBeEnabled();
  await checkAccessible(page);
  await page.screenshot({
    path: output + "/company-admins-390.png",
    fullPage: true,
  });
  await company.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, phone, newPassword);
  await expect(page).toHaveURL(/\/app\/overview/);
});

test("cash-only checkout needs no QR or UTR, retries safely and activates only after explicit receipt confirmation", async ({
  page,
  browser,
  workspace,
}) => {
  const owner = await ownerApi(),
    planName = "QA Cash Plan " + Date.now();
  const created = await owner.post("/api/platform/plans", {
    data: {
      name: planName,
      monthly_price: "1999",
      yearly_price: "19990",
      seats: 10,
    },
  });
  expect(created.status()).toBe(201);
  await login(page);
  await page.goto("/app/platform/billing");
  await page
    .getByRole("button", { name: "Edit payment instructions", exact: true })
    .click();
  const config = page.getByRole("dialog", {
    name: "Payment methods & instructions",
    exact: true,
  });
  await config
    .getByLabel("Accept UPI / QR payments", { exact: true })
    .uncheck();
  await config
    .getByLabel("Accept cash collection (COD)", { exact: true })
    .check();
  await config
    .getByLabel("Cash collection instructions", { exact: true })
    .fill("QA: Arrange collection at the Panipat office. No real payment.");
  await config
    .getByRole("button", { name: "Save changes", exact: true })
    .click();
  await expect(config).toHaveCount(0);
  const companyContext = await browser.newContext({
      viewport: { width: 390, height: 950 },
    }),
    companyPage = await companyContext.newPage();
  try {
    await login(companyPage, workspace.phone);
    await companyPage.goto("/app/billing");
    const card = companyPage.locator(".plan-card").filter({
      has: companyPage.getByRole("heading", { name: planName, exact: true }),
    });
    await expect(
      card.getByRole("button", { name: "Pay using QR", exact: true }),
    ).toHaveCount(0);
    await card
      .getByRole("button", { name: "Pay cash (COD)", exact: true })
      .click();
    const checkout = companyPage.getByRole("dialog", {
      name: "Pay cash for " + planName,
      exact: true,
    });
    await expect(
      checkout.getByLabel("Transaction reference / UTR", { exact: false }),
    ).toHaveCount(0);
    await expect(
      checkout.getByText(
        "QA: Arrange collection at the Panipat office. No real payment.",
        { exact: true },
      ),
    ).toBeVisible();
    await checkout.getByRole("checkbox", { name: /I will pay/ }).check();
    await companyPage.route(
      "**/api/billing/payments",
      async (route) => {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "temporary",
              message: "Temporary payment service failure",
            },
          }),
        });
      },
      { times: 1 },
    );
    await checkout
      .getByRole("button", { name: "Request cash collection", exact: true })
      .click();
    await expect(checkout.getByRole("alert")).toContainText(
      "Temporary payment service failure",
    );
    await expect(
      checkout.getByRole("checkbox", { name: /I will pay/ }),
    ).toBeChecked();
    await checkAccessible(companyPage);
    await checkout
      .getByRole("button", { name: "Request cash collection", exact: true })
      .click();
    await expect(checkout).toHaveCount(0);
    await expect(companyPage.locator(".billing-notice")).toContainText(
      "Your cash collection is pending",
    );
    await expect(
      card.getByRole("button", { name: "Pay cash (COD)", exact: true }),
    ).toBeDisabled();
    await companyPage.screenshot({
      path: output + "/cash-collection-pending-390.png",
      fullPage: true,
    });
    await page.goto("/app/platform/payments");
    await page
      .getByLabel("Payment method filter", { exact: true })
      .selectOption("cod");
    const paymentRow = page
      .getByRole("row")
      .filter({ hasText: workspace.name });
    await expect(paymentRow).toContainText("Cash (COD)");
    await paymentRow
      .getByRole("button", { name: "Verify payment", exact: true })
      .click();
    const review = page.getByRole("dialog", {
      name: "Verify payment from " + workspace.name,
      exact: true,
    });
    await review
      .getByLabel("Verification decision", { exact: true })
      .selectOption("approved");
    await review
      .getByLabel("Verification note", { exact: true })
      .fill("QA synthetic collection confirmation. No money transferred.");
    await review
      .getByRole("button", { name: "Save verification decision", exact: true })
      .click();
    await expect(review.getByRole("alert")).toContainText(
      "Confirm that the cash was received",
    );
    await review
      .getByRole("checkbox", { name: /I confirm.*cash was received/ })
      .check();
    await checkAccessible(page);
    await review
      .getByRole("button", { name: "Save verification decision", exact: true })
      .click();
    await expect(review).toHaveCount(0);
    await page.getByLabel("Payment review filter").selectOption("approved");
    await expect(paymentRow).toContainText("approved");
    await companyPage.reload();
    await expect(companyPage.locator(".subscription-strip")).toContainText(
      planName,
    );
    await expect(companyPage.locator(".subscription-strip")).toContainText(
      "active",
    );
    const payments = (await (await workspace.api.get("/api/billing")).json())
      .payments;
    expect(payments).toHaveLength(1);
    expect(payments[0].payment_method).toBe("cod");
    expect(payments[0].reference).toBeNull();
    await page.screenshot({
      path: output + "/cash-approved.png",
      fullPage: true,
    });
  } finally {
    const me = await (await workspace.api.get("/api/auth/me")).json();
    const billing = await (await owner.get("/api/platform/billing")).json();
    for (const p of billing.payments.filter(
      (p: { org_id: string; status: string }) =>
        p.org_id === me.organization.id && p.status === "pending",
    ))
      await owner.post(`/api/platform/payments/${p.id}/review`, {
        data: { status: "rejected", note: "QA cleanup: no cash collected" },
      });
    await companyContext.close();
    await owner.dispose();
  }
});

test("cash can be rejected without claiming receipt and both payment methods can be paused", async ({
  page,
  workspace,
}) => {
  const owner = await ownerApi();
  try {
    const planResult = await owner.post("/api/platform/plans", {
      data: {
        name: "QA Cash Reject " + Date.now(),
        monthly_price: "999",
        yearly_price: "9990",
        seats: 10,
      },
    });
    const plan = await planResult.json();
    const originalSubscription = (
      await (await workspace.api.get("/api/billing")).json()
    ).subscription;
    expect(
      (
        await owner.put("/api/platform/billing/config", {
          data: { upi_enabled: false, cod_enabled: true },
        })
      ).ok(),
    ).toBeTruthy();
    const result = await workspace.api.post("/api/billing/payments", {
      multipart: {
        plan_id: plan.id,
        cycle: "monthly",
        payment_method: "cod",
        quoted_amount: "999",
        request_id: crypto.randomUUID(),
      },
    });
    expect(result.status()).toBe(201);
    await login(page);
    await page.goto("/app/platform/payments");
    await page
      .getByRole("row")
      .filter({ hasText: workspace.name })
      .getByRole("button", { name: "Verify payment", exact: true })
      .click();
    await page
      .getByLabel("Verification decision", { exact: true })
      .selectOption("rejected");
    await page
      .getByLabel("Verification note", { exact: true })
      .fill("Cash not collected; company cancelled collection.");
    await page
      .getByRole("button", { name: "Save verification decision", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    const billing = await (await workspace.api.get("/api/billing")).json();
    expect(billing.payments[0].status).toBe("rejected");
    expect(billing.subscription).toEqual(originalSubscription);
    await owner.put("/api/platform/billing/config", {
      data: { upi_enabled: false, cod_enabled: false },
    });
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await login(page, workspace.phone);
    await page.goto("/app/billing");
    await expect(
      page.getByRole("button", { name: "Pay cash (COD)", exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Pay using QR", exact: true }),
    ).toHaveCount(0);
    await expect(
      page
        .getByText("Payment methods are paused. Contact the super admin.")
        .first(),
    ).toBeVisible();
  } finally {
    await owner.dispose();
  }
});
