import { expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { test } from "./fixtures";

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

test("enable share → open public page in a new context → contact buttons", async ({
  page,
  browser,
  workspace,
}) => {
  const setup = await workspace.api.post("/api/real-estate/setup");
  expect(setup.ok(), await setup.text()).toBeTruthy();
  const created = await workspace.api.post("/api/properties", {
    data: {
      title: "QA Share three-bedroom",
      reference: "QA-SHARE-1",
      property_type: "apartment",
      listing_type: "sale",
      city: "Gurugram",
      locality: "Sector 57",
      address: "Private Tower, Flat 9",
      developer: "Private Owner",
      price: "12500000",
      area_sqft: "1650",
      bedrooms: 3,
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const property = await created.json();
  await login(page, workspace.phone);
  await page.goto("/app/properties/" + property.id);
  await page.getByLabel("Upload property file").setInputFiles({
    name: "front.png",
    mimeType: "image/png",
    buffer: png,
  });
  await expect(page.getByText("front.png", { exact: true })).toBeVisible();
  const card = page.locator("#share");
  await expect(card).toContainText("Sharing is off");
  await card.getByRole("button", { name: "Turn on sharing" }).click();
  const link = card.getByLabel("Public link");
  await expect(link).toHaveValue(/\/p\/[A-Za-z0-9_-]{22,}$/);
  const url = new URL(await link.inputValue());
  await expect(card.getByRole("link", { name: "WhatsApp" })).toHaveAttribute(
    "href",
    /^https:\/\/wa\.me\/\?text=QA%20Share/,
  );
  const result = await new AxeBuilder({ page }).include("#share").analyze();
  expect(
    result.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);

  // A buyer with no session, on a 360 px phone.
  const buyer = await browser.newContext({
    viewport: { width: 360, height: 740 },
  });
  const pub = await buyer.newPage();
  const response = await pub.goto(url.pathname);
  expect(response?.status()).toBe(200);
  expect(response?.headers()["x-robots-tag"]).toContain("noindex");
  await expect(pub.getByRole("heading", { level: 1 })).toHaveText(
    "QA Share three-bedroom",
  );
  await expect(pub.getByText("₹1.25 Cr")).toBeVisible();
  await expect(pub.locator("body")).not.toContainText("Private Tower");
  await expect(pub.locator("body")).not.toContainText("QA-SHARE-1");
  await expect(pub.locator("meta[property='og:image']")).toHaveCount(1);
  await expect(pub.locator("meta[name='robots']")).toHaveAttribute(
    "content",
    /noindex/,
  );
  await expect(pub.getByRole("link", { name: /^Call / })).toHaveAttribute(
    "href",
    /^tel:\+91/,
  );
  await expect(pub.getByRole("link", { name: /^WhatsApp / })).toHaveAttribute(
    "href",
    /^https:\/\/wa\.me\/91\d{10}\?text=Hi%2C%20I%20saw%20QA%20Share/,
  );
  const overflow = await pub.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const photo = await pub.request.get(
    url.pathname.replace("/p/", "/api/public/p/") + "/photo/0",
  );
  expect(photo.headers()["content-type"]).toBe("image/jpeg");
  await buyer.close();

  // Turning it off makes the same URL a plain 404.
  await card.getByRole("button", { name: "Turn off" }).click();
  await expect(card).toContainText("Sharing is off");
  const gone = await browser.newContext();
  const after = await (await gone.newPage()).goto(url.pathname);
  expect(after?.status()).toBe(404);
  await gone.close();
});
