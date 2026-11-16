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
async function noSeriousAxe(page: Page) {
  await page.waitForFunction(() =>
    document.getAnimations().every((a) => a.playState !== "running"),
  );
  const result = await new AxeBuilder({ page }).analyze();
  expect(
    result.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
}

test("template → editable preview → open WhatsApp link logs an 'opened' note", async ({
  page,
  context,
  workspace,
}) => {
  const opened: string[] = [];
  await context.route("https://wa.me/**", async (route) => {
    opened.push(route.request().url());
    await route.fulfill({
      status: 200,
      body: "stub",
      contentType: "text/plain",
    });
  });
  const setup = await workspace.api.post("/api/real-estate/setup");
  expect(setup.ok(), await setup.text()).toBeTruthy();
  const make = async (name: string, phone: string, dnd = false) => {
    const r = await workspace.api.post("/api/leads", {
      data: { name, phone, source: "website", dnd },
    });
    expect(r.ok(), await r.text()).toBeTruthy();
    return r.json();
  };
  const lead = await make("Rohit Sharma", "9876541401");
  const quiet = await make("Quiet Client", "+919876541402", true);

  await login(page, workspace.phone);
  await page.goto("/app/message-templates");
  await expect(
    page.getByRole("heading", { name: "Message templates", level: 1 }),
  ).toBeVisible();
  for (const name of [
    "Introduction",
    "Site visit confirm",
    "Call not answered",
    "Property details",
  ])
    await expect(page.getByText(name, { exact: true })).toBeVisible();
  await noSeriousAxe(page);

  await page.goto("/app/leads/" + lead.id);
  await page.getByRole("button", { name: "Templates" }).click();
  const dialog = page.getByRole("dialog", { name: "Message with a template" });
  await dialog
    .getByLabel("Template", { exact: true })
    .selectOption({ label: "Introduction · New lead" });
  const preview = dialog.getByLabel("Message preview");
  await expect(preview).toHaveValue(/^Namaste Rohit ji, main /);
  await expect(preview).not.toHaveValue(/\{\{/);
  await preview.fill((await preview.inputValue()) + " नमस्ते 🙏");
  await noSeriousAxe(page);
  const link = dialog.getByRole("link", { name: /Open WhatsApp/ });
  const href = (await link.getAttribute("href")) || "";
  expect(href.startsWith("https://wa.me/919876541401?text=")).toBeTruthy();
  expect(decodeURIComponent(href.split("?text=")[1])).toContain("नमस्ते 🙏");
  await expect(dialog.getByRole("link", { name: "Open SMS" })).toHaveAttribute(
    "href",
    /^sms:\+919876541401\?body=/,
  );
  const popup = page.waitForEvent("popup");
  await link.click();
  await (await popup).close();
  expect(opened[0]).toContain("wa.me/919876541401");
  await dialog.getByRole("button", { name: "Close" }).click();
  await page.getByRole("button", { name: "Notes", exact: true }).click();
  await expect(
    page.getByText(/WhatsApp message opened using template Introduction/),
  ).toBeVisible();
  await expect(page.getByText(/message sent/i)).toHaveCount(0);

  await page.goto("/app/leads/" + quiet.id);
  await expect(page.getByRole("button", { name: "Templates" })).toBeDisabled();
});
