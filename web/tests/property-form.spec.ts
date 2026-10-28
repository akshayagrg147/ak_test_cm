import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
import { test } from "./fixtures";

async function openForm(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill("LocalCRM!2026");
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
  await page.goto("/app/properties");
  await page.getByRole("button", { name: "Add property", exact: true }).click();
}

test("property form adapts all types and rental wording on a narrow screen", async ({
  page,
  workspace,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openForm(page, workspace.phone);
  const dialog = page.getByRole("dialog");
  const project = page.getByText("Project / owner details (optional)", {
    exact: true,
  });
  await expect(page.getByLabel("Project RERA number")).toBeHidden();
  for (const type of [
    "apartment",
    "villa",
    "plot",
    "office",
    "retail",
    "warehouse",
    "other",
  ]) {
    await page.getByLabel("Property type", { exact: true }).selectOption(type);
    const home = ["apartment", "villa"].includes(type);
    await expect(page.getByLabel("Bedrooms", { exact: true })).toHaveCount(
      home ? 1 : 0,
    );
    await expect(page.getByLabel("Bathrooms", { exact: true })).toHaveCount(
      home ? 1 : 0,
    );
    await expect(page.getByLabel("Washrooms", { exact: true })).toHaveCount(
      !home && type !== "plot" ? 1 : 0,
    );
    await expect(
      page.getByLabel(type === "plot" ? "Plot area (sq ft)" : "Area (sq ft)", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByLabel(
        type === "plot" ? "Plot handover" : "Possession / handover",
        { exact: true },
      ),
    ).toBeVisible();
    await page.getByLabel("Listing type", { exact: true }).selectOption("rent");
    await expect(
      page.getByLabel("Monthly rent (₹)", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByLabel("Available from", { exact: true }),
    ).toBeVisible();
    await page.getByLabel("Listing type", { exact: true }).selectOption("sale");
    await expect(
      page.getByLabel("Asking price (₹)", { exact: true }),
    ).toBeVisible();
  }
  // The disclosure also works from the keyboard and keeps values when closed.
  await project.focus();
  await project.press("Enter");
  await page.getByLabel("Project RERA number").fill("DEMO-RERA-REF");
  await project.click();
  await expect(page.getByLabel("Project RERA number")).toBeHidden();
  await project.click();
  await expect(page.getByLabel("Project RERA number")).toHaveValue(
    "DEMO-RERA-REF",
  );
  const axe = await new AxeBuilder({ page }).include("dialog").analyze();
  expect(
    axe.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  expect(
    await dialog.evaluate(
      (element) => element.scrollWidth <= element.clientWidth + 1,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button", { name: "Add property", exact: true }).click();
  await expect(page.getByLabel("Property type", { exact: true })).toHaveValue(
    "apartment",
  );
  await expect(page.getByLabel("Project RERA number")).toBeHidden();
});

test("create and edit clear irrelevant rooms while keeping project details", async ({
  page,
  workspace,
}) => {
  await openForm(page, workspace.phone);
  await page
    .getByLabel("Property title", { exact: true })
    .fill("QA type-aware property");
  await page.getByLabel("Inventory reference").fill("QA-TYPE-001");
  await page.getByLabel("City", { exact: true }).fill("Panipat");
  await page.getByLabel("Asking price (₹)", { exact: true }).fill("4800000");
  await page.getByLabel("Area (sq ft)", { exact: true }).fill("1200");
  await page.getByLabel("Bedrooms", { exact: true }).fill("0");
  await page.getByLabel("Bathrooms", { exact: true }).fill("1");
  await page
    .getByText("Project / owner details (optional)", { exact: true })
    .click();
  await page.getByLabel("Project / building").fill("Fictional QA project");
  await page.getByLabel("Project RERA number").fill("DEMO-REF-001");
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  let saved = (await (await workspace.api.get("/api/properties")).json())
    .items[0];
  expect(saved).toMatchObject({
    bedrooms: 0,
    bathrooms: 1,
    project: "Fictional QA project",
  });
  await page
    .getByRole("link", { name: "QA type-aware property", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Edit property", exact: true })
    .click();
  await expect(page.getByLabel("Project RERA number")).toHaveValue(
    "DEMO-REF-001",
  );
  await page.getByLabel("Property type", { exact: true }).selectOption("plot");
  await expect(page.getByLabel("Bedrooms", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Bathrooms", { exact: true })).toHaveCount(0);
  // Switching back must not resurrect hidden counts.
  await page.getByLabel("Property type", { exact: true }).selectOption("villa");
  await expect(page.getByLabel("Bedrooms", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Bathrooms", { exact: true })).toHaveValue("");
  await page.getByLabel("Property type", { exact: true }).selectOption("plot");
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  saved = await (await workspace.api.get("/api/properties/" + saved.id)).json();
  expect(saved).toMatchObject({
    property_type: "plot",
    bedrooms: null,
    bathrooms: null,
    rera_number: "DEMO-REF-001",
  });
  await expect(page.getByText("Plot handover", { exact: true })).toBeVisible();
  await expect(page.locator(".estate-specs")).not.toContainText(
    /bedrooms|bathrooms/,
  );
  await page
    .getByRole("button", { name: "Edit property", exact: true })
    .click();
  await page
    .getByLabel("Property type", { exact: true })
    .selectOption("office");
  await page.getByLabel("Washrooms", { exact: true }).fill("2");
  await page.getByLabel("Listing type", { exact: true }).selectOption("rent");
  await page.getByLabel("Monthly rent (₹)", { exact: true }).fill("25000");
  await page.getByLabel("Available from", { exact: true }).fill("Immediately");
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("2 washrooms", { exact: true })).toBeVisible();
  await expect(page.getByText("Available from", { exact: true })).toBeVisible();
  saved = await (await workspace.api.get("/api/properties/" + saved.id)).json();
  expect(saved).toMatchObject({
    listing_type: "rent",
    property_type: "office",
    bedrooms: null,
    bathrooms: 2,
    possession: "Immediately",
  });
});

test("validation and save retry retain type-specific and optional values", async ({
  page,
  workspace,
}) => {
  const existing = await workspace.api.post("/api/properties", {
    data: {
      title: "QA existing plot",
      reference: "QA-DUP-001",
      property_type: "plot",
      city: "Panipat",
      price: "1000000",
      area_sqft: "900",
    },
  });
  expect(existing.status()).toBe(201);
  await openForm(page, workspace.phone);
  await page.getByLabel("Property type", { exact: true }).selectOption("plot");
  await page
    .getByLabel("Property title", { exact: true })
    .fill("QA retried plot");
  await page.getByLabel("Inventory reference").fill("QA-DUP-001");
  await page.getByLabel("City", { exact: true }).fill("Panipat");
  await page.getByLabel("Asking price (₹)", { exact: true }).fill("0");
  await page.getByLabel("Plot area (sq ft)", { exact: true }).fill("900");
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page
      .getByLabel("Asking price (₹)", { exact: true })
      .evaluate((input: HTMLInputElement) => input.validity.rangeUnderflow),
  ).toBeTruthy();
  await page.getByLabel("Asking price (₹)", { exact: true }).fill("2400000");
  await page
    .getByText("Project / owner details (optional)", { exact: true })
    .click();
  await page.getByLabel("Developer / owner").fill("Fictional QA owner");
  await page
    .getByText("Project / owner details (optional)", { exact: true })
    .click();
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "reference already exists",
  );
  await expect(page.getByLabel("Property type", { exact: true })).toHaveValue(
    "plot",
  );
  await expect(
    page.getByLabel("Asking price (₹)", { exact: true }),
  ).toHaveValue("2400000");
  await page.getByLabel("Inventory reference").fill("QA-RETRY-001");
  await page
    .getByRole("button", { name: "Save property", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const inventory = (
    await (await workspace.api.get("/api/properties?q=QA-RETRY-001")).json()
  ).items;
  expect(inventory).toHaveLength(1);
  expect(inventory[0]).toMatchObject({
    bedrooms: null,
    bathrooms: null,
    developer: "Fictional QA owner",
    property_type: "plot",
  });
});
