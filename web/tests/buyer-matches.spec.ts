import { expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { test } from "./fixtures";

const password = "LocalCRM!2026";
async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/(overview|platform)/);
}
async function settled(page: Page) {
  await page.waitForFunction(() =>
    document.getAnimations().every((a) => a.playState !== "running"),
  );
}

test("add property → see matching buyer → open client", async ({
  page,
  workspace,
}) => {
  const enabled = await workspace.api.post("/api/real-estate/setup");
  expect(enabled.ok(), await enabled.text()).toBeTruthy();
  const buyers = [];
  for (const [name, phone, dnd] of [
    ["Matching Buyer", "+919876541201", false],
    ["Quiet Buyer", "+919876541202", true],
  ] as const) {
    const created = await workspace.api.post("/api/leads", {
      data: { name, phone, source: "website", dnd },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const lead = await created.json();
    const saved = await workspace.api.put(
      `/api/leads/${lead.id}/requirements`,
      {
        data: {
          purpose: "buy",
          budget_min: "10000000",
          budget_max: "15000000",
          city: "Gurugram",
          localities: ["sector 57"],
          property_types: ["apartment"],
          bedrooms: 3,
        },
      },
    );
    expect(saved.ok(), await saved.text()).toBeTruthy();
    buyers.push(lead);
  }
  await login(page, workspace.phone);
  await page.goto("/app/properties");
  await page.getByRole("button", { name: "Add property", exact: true }).click();
  await page
    .getByLabel("Property title", { exact: true })
    .fill("QA Sector 57 three-bedroom");
  await page.getByLabel("Inventory reference").fill("QA-S57-3");
  await page.getByLabel("City", { exact: true }).fill("Gurugram");
  await page.getByLabel("Locality", { exact: true }).fill("Sector 57 ");
  await page.getByLabel("Asking price (₹)").fill("12000000");
  await page.getByLabel("Area (sq ft)").fill("1650");
  await page.getByLabel("Bedrooms", { exact: true }).fill("3");
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const notice = page.getByRole("status").filter({ hasText: "saved buyer" });
  await expect(notice).toContainText(
    "1 saved buyer matches QA Sector 57 three-bedroom",
  );
  await expect(
    page.getByRole("link", {
      name: "1 saved buyer matches QA Sector 57 three-bedroom",
    }),
  ).toHaveText("1 buyer");
  await notice.getByRole("link", { name: "View" }).click();
  const card = page.locator("#matching-buyers");
  await expect(
    card.getByRole("heading", { name: "Matching buyers (1)" }),
  ).toBeVisible();
  await expect(card).toContainText("Matching Buyer");
  await expect(card).not.toContainText("Quiet Buyer");
  await expect(card).toContainText("1 more matches but is do-not-contact.");
  await settled(page);
  const result = await new AxeBuilder({ page }).analyze();
  expect(
    result.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  await card.getByRole("link", { name: "Open client" }).click();
  await expect(page).toHaveURL(new RegExp("/app/leads/" + buyers[0].id));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Matching Buyer",
  );
});
