import { expect, request, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
import { test } from "./fixtures";

const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/real-estate") + "/screenshots";
mkdirSync(output, { recursive: true });
const password = "LocalCRM!2026";
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGMUCTjBAAJMYJKBgQEAEkIBMLmziVsAAAAASUVORK5CYII=",
  "base64",
);
async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/(overview|platform)/);
}
const localTime = (date: Date) =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);

test("super admin edits company branding, uploads logo and manages trial seats", async ({
  page,
  workspace,
}) => {
  await login(page, "+919900000001");
  await page.getByLabel("Search companies").fill(workspace.name);
  const row = page.getByRole("row").filter({ hasText: workspace.name });
  await row.getByRole("button", { name: "Edit profile", exact: true }).click();
  await page.getByLabel("Workspace brand name").fill("Orchard Realty QA");
  await page.getByLabel("Company city", { exact: true }).fill("Pune");
  await page
    .getByLabel("Company email", { exact: true })
    .fill("qa@example.com");
  await page.getByRole("button", { name: "Save company profile" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(row).toContainText("Pune");
  await row.getByRole("button", { name: "Manage", exact: true }).click();
  await page
    .getByLabel("Upload company logo")
    .setInputFiles({ name: "qa-logo.png", mimeType: "image/png", buffer: png });
  await expect(
    page.getByRole("img", { name: "Company logo", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Manage subscription" }).click();
  const nested = page.getByRole("dialog", {
    name: "Manage company subscription",
    exact: true,
  });
  await nested.getByLabel("Maximum active team seats").fill("10");
  await nested
    .getByLabel("Subscription starts")
    .fill(new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }));
  await nested.getByLabel("Subscription ends").fill(
    new Date(Date.now() + 1209600000).toLocaleDateString("en-CA", {
      timeZone: "Asia/Kolkata",
    }),
  );
  await nested.getByRole("button", { name: "Save changes" }).click();
  await expect(nested).toHaveCount(0);
  await expect(page.locator(".subscription-strip")).toContainText(
    "1 / 10 seats",
  );
  await page.screenshot({
    path: output + "/super-admin-company-profile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await expect(row).toContainText("1 / 10");
});

test("real estate buyer, property upload, matching, visit and reservation through closing", async ({
  page,
  workspace,
}) => {
  const enabled = await workspace.api.post("/api/real-estate/setup");
  expect(enabled.ok(), await enabled.text()).toBeTruthy();
  const buyer = await workspace.api.post("/api/leads", {
    data: {
      name: "QA Property Buyer",
      phone: "+919876540101",
      source: "99acres",
    },
  });
  expect(buyer.ok(), await buyer.text()).toBeTruthy();
  const lead = await buyer.json();
  await login(page, workspace.phone);
  await page.goto("/app/properties");
  await page.getByRole("button", { name: "Add property", exact: true }).click();
  await page
    .getByLabel("Property title", { exact: true })
    .fill("QA Orchard two-bedroom residence");
  await page.getByLabel("Inventory reference").fill("QA-A1204");
  await page
    .getByText("Project / owner details (optional)", { exact: true })
    .click();
  await page.getByLabel("Project / building").fill("Orchard Residences");
  await page.getByLabel("City", { exact: true }).fill("Pune");
  await page.getByLabel("Locality", { exact: true }).fill("Baner");
  await page.getByLabel("Asking price (₹)").fill("7800000");
  await page.getByLabel("Area (sq ft)").fill("1200");
  await page.getByLabel("Bedrooms", { exact: true }).fill("2");
  await page.getByLabel("Bathrooms", { exact: true }).fill("2");
  await page.getByLabel("Amenities", { exact: true }).fill("Parking, Security");
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("link", {
      name: "QA Orchard two-bedroom residence",
      exact: true,
    })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "QA Orchard two-bedroom residence",
  );
  await page.getByLabel("Upload property file").setInputFiles({
    name: "qa-floor-plan.png",
    mimeType: "image/png",
    buffer: png,
  });
  await expect(
    page.getByText("qa-floor-plan.png", { exact: true }),
  ).toBeVisible();
  const property = (await (await workspace.api.get("/api/properties")).json())
    .items[0];
  await page.screenshot({
    path: output + "/property-detail.png",
    fullPage: true,
  });
  await page.goto("/app/leads/" + lead.id);
  await page
    .getByRole("button", { name: "Property brief", exact: true })
    .click();
  await page.getByRole("button", { name: "Add requirements" }).click();
  await page.getByLabel("Preferred city").fill("Pune");
  await page.getByLabel("Maximum budget (₹)").fill("8000000");
  await page.getByLabel("Preferred localities").fill("Baner");
  await page.getByRole("checkbox", { name: "apartment", exact: true }).check();
  await page.getByLabel("Bedrooms required").fill("2");
  await page.getByLabel("Purchase / move timeline").fill("Within 3 months");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Save changes" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: property.title, exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Schedule visit", exact: true })
    .click();
  await page
    .getByLabel("Visit date & time")
    .fill(localTime(new Date(Date.now() + 86400000)));
  await expect(page.getByLabel("Property", { exact: true })).toHaveValue(
    property.id,
  );
  await page.getByRole("button", { name: "Save site visit" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goto("/app/site-visits");
  await expect(page.locator(".visit-card")).toContainText("QA Property Buyer");
  await page.getByRole("button", { name: "Reschedule", exact: true }).click();
  await page
    .getByLabel("Visit date & time")
    .fill(localTime(new Date(Date.now() + 172800000)));
  await page.getByRole("button", { name: "Save site visit" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.screenshot({ path: output + "/site-visits.png", fullPage: true });
  await page.goto("/app/bookings");
  await page
    .getByRole("button", { name: "Create booking", exact: true })
    .click();
  await page.getByLabel("Buyer enquiry", { exact: true }).selectOption(lead.id);
  await page.getByLabel("Property", { exact: true }).selectOption(property.id);
  await page
    .getByLabel("Booking agent", { exact: true })
    .selectOption(workspace.user);
  await page
    .getByLabel("Booking reference", { exact: true })
    .fill("QA-BOOKING-01");
  await page.getByLabel("Agreed deal value (₹)").fill("7700000");
  await page.getByLabel("Token amount recorded (₹)").fill("100000");
  await page.getByLabel("Agreed commission (₹)").fill("77000");
  await page.getByRole("button", { name: "Reserve property" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("row").filter({ hasText: "QA-BOOKING-01" }),
  ).toContainText("reserved");
  for (const stage of ["booked", "closed"]) {
    await page.getByRole("button", { name: "Update stage" }).click();
    await page.getByLabel("Next stage").selectOption(stage);
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Save changes" })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(
      page.getByRole("row").filter({ hasText: "QA-BOOKING-01" }),
    ).toContainText(stage);
  }
  expect(
    await (await workspace.api.get("/api/properties/" + property.id)).json(),
  ).toMatchObject({ status: "sold" });
  await page.screenshot({ path: output + "/bookings.png", fullPage: true });
});

test("company QR payment stays pending until super admin verifies and activates it", async ({
  page,
  browser,
  workspace,
}) => {
  const owner = await request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  const auth = await owner.post("/api/auth/login", {
    data: { phone: "+919900000001", password },
  });
  const headers = {
    Authorization: "Bearer " + (await auth.json()).access_token,
  };
  const planName = "QA Growth " + Date.now();
  const response = await owner.post("/api/platform/plans", {
    headers,
    data: {
      name: planName,
      monthly_price: "1999",
      yearly_price: "19990",
      seats: 10,
      description: "QA fixture. No real payment.",
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  await owner.put("/api/platform/billing/config", {
    headers,
    data: {
      payee_name: "QA TEST ACCOUNT — NOT FOR PAYMENT",
      upi_id: "qa-fixture@example",
      instructions: "Isolated QA fixture only. Do not transfer real money.",
    },
  });
  expect(
    (
      await owner.post("/api/platform/billing/qr", {
        headers,
        multipart: {
          file: {
            name: "test-image-not-payment-qr.png",
            mimeType: "image/png",
            buffer: png,
          },
        },
      })
    ).ok(),
  ).toBeTruthy();
  await login(page, workspace.phone);
  await page.goto("/app/billing");
  const card = page.locator(".plan-card").filter({
    has: page.getByRole("heading", { name: planName, exact: true }),
  });
  await card.getByRole("button", { name: "Pay using QR" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Submitting a reference does not confirm payment",
  );
  const reference = "QA-TEST-REF-" + Date.now();
  await page
    .getByLabel("Transaction reference / UTR", { exact: false })
    .fill(reference);
  await page.getByLabel("Payment receipt (optional)").setInputFiles({
    name: "test-receipt.png",
    mimeType: "image/png",
    buffer: png,
  });
  await page.getByRole("checkbox", { name: /I have paid/ }).check();
  await page
    .getByRole("button", { name: "Submit payment for verification" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".billing-notice")).toContainText(
    "awaiting verification",
  );
  await expect(
    page.getByRole("row").filter({ hasText: reference }),
  ).toContainText("pending");
  await page.screenshot({
    path: output + "/payment-pending.png",
    fullPage: true,
  });
  const ownerContext = await browser.newContext();
  const ownerPage = await ownerContext.newPage();
  await login(ownerPage, "+919900000001");
  await ownerPage.goto("/app/platform/payments");
  const row = ownerPage.getByRole("row").filter({ hasText: reference });
  await row.getByRole("button", { name: "Verify payment" }).click();
  await ownerPage.getByLabel("Verification decision").selectOption("approved");
  await ownerPage
    .getByLabel("Verification note")
    .fill("QA fixture verification. No actual bank payment.");
  await ownerPage
    .getByRole("button", { name: "Save verification decision" })
    .click();
  await expect(ownerPage.getByRole("dialog")).toHaveCount(0);
  await ownerPage.getByLabel("Payment review filter").selectOption("approved");
  await expect(
    ownerPage.getByRole("row").filter({ hasText: reference }),
  ).toContainText("approved");
  await page.reload();
  await expect(page.locator(".subscription-strip")).toContainText(planName);
  await expect(page.locator(".subscription-strip")).toContainText("active");
  await expect(page.locator(".subscription-strip")).toContainText("1 of 10");
  await page.screenshot({
    path: output + "/subscription-active.png",
    fullPage: true,
  });
  await ownerPage.screenshot({
    path: output + "/super-admin-payments.png",
    fullPage: true,
  });
  await ownerContext.close();
  await owner.dispose();
});

test("real estate and billing screens are accessible and fit narrow web viewports", async ({
  page,
  workspace,
}) => {
  await login(page, workspace.phone);
  for (const route of ["properties", "site-visits", "bookings", "billing"]) {
    await page.goto("/app/" + route);
    await expect(page.locator(".skeletons")).toHaveCount(0);
    const result = await new AxeBuilder({ page }).analyze();
    expect(
      result.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact || ""),
      ),
    ).toEqual([]);
    for (const width of [390, 768, 1440]) {
      await page.setViewportSize({ width, height: 950 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBeTruthy();
      await page.screenshot({
        path: `${output}/${route}-${width}.png`,
        fullPage: true,
      });
    }
  }
});
