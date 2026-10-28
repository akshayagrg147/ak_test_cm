import { expect, type Page } from "@playwright/test";
import { test, type Workspace } from "./fixtures";
import { mkdirSync } from "node:fs";

const screenshots =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/readability") + "/screenshots";
mkdirSync(screenshots, { recursive: true });

async function readable(page: Page, minimum = 14) {
  await page.evaluate(() => document.fonts.ready);
  const smallText = await page.locator("body *").evaluateAll(
    (elements, size) =>
      elements.flatMap((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        const hasText = [...element.childNodes].some(
          (node) =>
            node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
        );
        if (
          !hasText ||
          !rect.width ||
          !rect.height ||
          style.visibility === "hidden" ||
          element.closest("svg, [aria-hidden='true'], option, script, style")
        )
          return [];
        return parseFloat(style.fontSize) < size
          ? [{ text: element.textContent?.slice(0, 80), size: style.fontSize }]
          : [];
      }),
    minimum,
  );
  expect(smallText, "Visible text should remain comfortably readable").toEqual(
    [],
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
    "The page should fit without horizontal scrolling",
  ).toBeTruthy();
}

async function login(page: Page, workspace: Workspace) {
  await page.goto("/login");
  await page.getByLabel("Phone number").fill(workspace.phone);
  await page.getByLabel("Password", { exact: true }).fill("LocalCRM!2026");
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page.locator(".stat").first()).toBeVisible();
}

async function visit(page: Page, route: string) {
  await page.goto("/app/" + route);
  await expect(page.locator(".page-heading h1")).toBeVisible();
  await expect(page.locator(".skeletons")).toHaveCount(0);
  await expect(page.locator(".workspace-main .error-box")).toHaveCount(0);
}

test("public and login text, labels and controls are readable on small and large screens", async ({
  page,
}) => {
  for (const width of [320, 360, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await expect(page.locator("#contact")).toBeVisible();
    await readable(page);
    await page.goto("/login");
    await expect(page.getByLabel("Phone number")).toBeVisible();
    await readable(page);
    for (const label of ["Phone number", "Password"]) {
      const metrics = await page
        .getByLabel(label, { exact: label === "Password" })
        .evaluate((el) => ({
          font: parseFloat(getComputedStyle(el).fontSize),
          height: el.getBoundingClientRect().height,
        }));
      expect(metrics.font).toBe(16);
      expect(metrics.height).toBeGreaterThanOrEqual(44);
    }
    await page.screenshot({
      path: `${screenshots}/readable-login-${width}.png`,
      fullPage: true,
    });
  }
});

test("all workspace areas and the lead editor retain readable text and responsive layouts", async ({
  page,
  workspace,
}) => {
  test.setTimeout(90000);
  await login(page, workspace);
  for (const width of [360, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of [
      "overview",
      "leads",
      "tasks",
      "phone-calls",
      "lost",
      "reports",
      "attendance",
      "approvals",
      "team",
      "payroll",
      "automations",
      "integrations",
      "audit",
      "backups",
      "settings",
      "security",
    ]) {
      await visit(page, route);
      await readable(page);
      if (["overview", "leads", "settings"].includes(route)) {
        await page.screenshot({
          path: `${screenshots}/readable-${route}-${width}.png`,
          fullPage: true,
        });
      }
    }
    await visit(page, "leads");
    await page
      .getByRole("button", { name: "Add a lead", exact: true })
      .first()
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await readable(page);
    const fields = await page
      .getByRole("dialog")
      .locator(".field > span, input:not([type='checkbox']), textarea, select")
      .evaluateAll((els) =>
        els.map((el) => parseFloat(getComputedStyle(el).fontSize)),
      );
    expect(Math.min(...fields)).toBe(16);
    expect(Math.max(...fields)).toBe(16);
    await expect(
      page.getByLabel("Property / project interests", { exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: `${screenshots}/readable-editor-${width}.png`,
      fullPage: true,
    });
    await page.keyboard.press("Escape");
  }
});

test("browser text preferences can double the text while navigation and forms remain usable", async ({
  page,
  workspace,
}) => {
  await login(page, workspace);
  // A larger default browser font must scale the rem-based typography too.
  await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
  await readable(page, 28);
  await page.screenshot({
    path: `${screenshots}/readable-text-200-percent.png`,
    fullPage: true,
  });
  await page.setViewportSize({ width: 720, height: 1000 });
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page
    .getByRole("navigation", { name: "Work areas", exact: true })
    .getByRole("link", { name: "Sales", exact: true })
    .click();
  await expect(page.locator(".page-heading h1")).toBeVisible();
  await expect(page.locator(".skeletons")).toHaveCount(0);
  await readable(page, 28);
  await page
    .getByRole("button", { name: "Add a lead", exact: true })
    .first()
    .click();
  await page.getByLabel("Customer / buyer name").fill("Readable form preview");
  await page
    .getByLabel("Property / project interests", { exact: true })
    .fill("Training and support");
  await readable(page, 28);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
