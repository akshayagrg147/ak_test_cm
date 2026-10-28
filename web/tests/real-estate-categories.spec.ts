import { randomInt } from "node:crypto";
import { mkdirSync } from "node:fs";
import { expect, type Page } from "@playwright/test";
import { test, type Workspace } from "./fixtures";

const propertyLabels = [
  "Apartment",
  "Villa",
  "Plot",
  "Office",
  "Retail",
  "Warehouse",
  "Other",
];
const healthcareLabels = [
  "Pharmaceutical",
  "Ayurvedic",
  "Homeopathic",
  "Nutraceutical",
  "Generic",
];
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/category-correction") +
  "/screenshots";
mkdirSync(output, { recursive: true });

async function login(page: Page, workspace: Workspace) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(workspace.phone);
  await page.getByLabel("Password", { exact: true }).fill("LocalCRM!2026");
  await page
    .getByRole("button", { name: "Sign in to your workspace", exact: true })
    .click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.goto("/app/leads");
  await expect(
    page.getByRole("heading", { name: "Your leads", exact: true }),
  ).toBeVisible();
}
async function more(page: Page) {
  await page.getByRole("button", { name: /^More filters/ }).click();
  return page.getByRole("dialog", { name: "Filter leads", exact: true });
}
async function options(page: Page, label: string) {
  await expect(page.getByLabel(label, { exact: true })).toBeEnabled();
  return page
    .getByLabel(label, { exact: true })
    .locator("option")
    .allTextContents();
}

test("converted real estate company offers property categories, saves them and filters matching buyers", async ({
  page,
  workspace,
}) => {
  const old = await workspace.api.post("/api/leads", {
    data: {
      name: "Previous customer",
      phone: "+9195" + randomInt(10000000, 99999999),
      category: "ayurvedic",
      notes: "Preserve existing customer",
    },
  });
  expect(old.status()).toBe(201);
  const oldLead = await old.json();
  expect(
    (
      await workspace.api.post("/api/saved-views", {
        data: {
          name: "Previous customer category",
          kind: "leads",
          filters: { category: "ayurvedic" },
        },
      })
    ).status(),
  ).toBe(201);
  for (const [key, label, active] of [
    ["farmhouse", "Farmhouse", true],
    ["old-site", "Retired site", false],
  ] as const) {
    const created = await workspace.api.post("/api/definitions", {
      data: { kind: "category", key, label, active },
    });
    expect(created.status()).toBe(201);
  }
  expect(
    (await workspace.api.post("/api/real-estate/setup")).ok(),
  ).toBeTruthy();
  await login(page, workspace);
  await more(page);
  const categories = await options(page, "Property category");
  expect(categories.sort()).toEqual(
    ["All categories", ...propertyLabels, "Farmhouse"].sort(),
  );
  for (const label of healthcareLabels) expect(categories).not.toContain(label);
  expect(categories).not.toContain("Retired site");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();

  await page.getByRole("button", { name: "Add a lead", exact: true }).click();
  await page
    .getByLabel("Customer / buyer name", { exact: true })
    .fill("Panipat plot buyer");
  await page
    .getByLabel("Phone number", { exact: true })
    .fill("+9194" + randomInt(10000000, 99999999));
  const formOptions = await options(page, "Property category");
  expect(formOptions.sort()).toEqual(
    ["Select…", ...propertyLabels, "Farmhouse"].sort(),
  );
  await expect(
    page.getByLabel("Drug license number", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByLabel("Property category", { exact: true })
    .selectOption("plot");
  await page.getByRole("button", { name: "Create lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await more(page);
  await page
    .getByLabel("Property category", { exact: true })
    .selectOption("plot");
  await page
    .getByRole("button", { name: "Apply filters", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Panipat plot buyer");
  await page.reload();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.locator("tbody a.name-cell").click();
  await page.getByRole("button", { name: "Edit details", exact: true }).click();
  await expect(
    page.getByLabel("Property category", { exact: true }),
  ).toHaveValue("plot");
  await page
    .getByLabel("Property category", { exact: true })
    .selectOption("apartment");
  await page.getByRole("button", { name: "Save lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.locator(".detail-list:not(.score-factors)")).toContainText(
    "Apartment",
  );
  await page.goto("/app/leads?category=apartment");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Panipat plot buyer");
  const exported = await workspace.api.get(
    "/api/leads/export?category=apartment",
  );
  expect(await exported.text()).toContain("Panipat plot buyer");
  expect(await exported.text()).not.toContain("Previous customer");
  await more(page);
  await page.screenshot({
    path: output + "/real-estate-category-options.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Cancel", exact: true }).click();

  // An explicitly selected historical category stays interpretable and removable.
  await page
    .getByRole("button", { name: "Previous customer category", exact: true })
    .click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Previous customer");
  await more(page);
  await expect(
    page.getByLabel("Property category", { exact: true }),
  ).toHaveValue("ayurvedic");
  expect(await options(page, "Property category")).toContain(
    "Ayurvedic (previous category)",
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.goto("/app/leads/" + oldLead.id);
  await page.getByRole("button", { name: "Edit details", exact: true }).click();
  await expect(
    page.getByLabel("Property category", { exact: true }),
  ).toHaveValue("ayurvedic");
  expect(await options(page, "Property category")).toContain(
    "Ayurvedic (previous category)",
  );
  await page
    .getByLabel("Initial notes", { exact: true })
    .fill("Preserved during edit");
  await page.getByRole("button", { name: "Save lead", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(
    (await (await workspace.api.get("/api/leads/" + oldLead.id)).json())
      .category,
  ).toBe("ayurvedic");
});

test("healthcare categories remain available in a general pharma workspace", async ({
  page,
  workspace,
}) => {
  expect(
    (
      await workspace.api.put("/api/settings", {
        data: { pharma_enabled: true },
      })
    ).ok(),
  ).toBeTruthy();
  await login(page, workspace);
  await more(page);
  const categories = await options(page, "Lead category");
  for (const label of healthcareLabels) expect(categories).toContain(label);
  expect(categories).not.toContain("Apartment");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page
    .locator(".page-heading")
    .getByRole("button", { name: "Add a lead", exact: true })
    .click();
  await expect(
    page.getByLabel("Drug license number", { exact: true }),
  ).toBeVisible();
  const form = await options(page, "Primary category");
  for (const label of healthcareLabels) expect(form).toContain(label);
});
