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

test("WhatsApp click-to-chat opens wa.me with a greeting, logs 'opened' and is hidden for do-not-contact", async ({
  page,
  context,
  workspace,
}) => {
  // Never reach the real WhatsApp site from tests.
  const opened: string[] = [];
  await context.route("https://wa.me/**", async (route) => {
    opened.push(route.request().url());
    await route.fulfill({
      status: 200,
      body: "stub",
      contentType: "text/plain",
    });
  });
  const make = async (name: string, phone: string, dnd = false) => {
    const r = await workspace.api.post("/api/leads", {
      data: { name, phone, source: "website", dnd },
    });
    expect(r.ok(), await r.text()).toBeTruthy();
    return r.json();
  };
  const lead = await make("Ravi Kumar", "+919876541301");
  const quiet = await make("Quiet Client", "+919876541302", true);
  await login(page, workspace.phone);
  await page.goto("/app/leads/" + lead.id);
  const chat = page.getByRole("link", {
    name: "Open WhatsApp chat with Ravi Kumar",
  });
  await expect(chat).toBeVisible();
  const href = (await chat.getAttribute("href")) || "";
  expect(href.startsWith("https://wa.me/919876541301?text=")).toBeTruthy();
  const text = decodeURIComponent(href.split("?text=")[1]);
  expect(text).toContain("Namaste Ravi ji");
  await expect(chat).toHaveAttribute("target", "_blank");
  await expect(chat).toHaveAttribute("rel", /noopener/);
  const result = await new AxeBuilder({ page }).analyze();
  expect(
    result.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);

  const popup = page.waitForEvent("popup");
  await chat.click();
  await (await popup).close();
  expect(opened[0]).toContain("wa.me/919876541301");
  await page.reload();
  await expect(page.getByText(/Opened a WhatsApp chat/).first()).toBeVisible();
  await expect(page.getByText(/WhatsApp.*sent/i)).toHaveCount(0);

  await page.goto("/app/leads/" + quiet.id);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Quiet Client",
  );
  await expect(
    page.getByRole("link", { name: /Open WhatsApp chat/ }),
  ).toHaveCount(0);
});
