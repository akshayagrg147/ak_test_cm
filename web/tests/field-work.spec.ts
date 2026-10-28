import { randomInt } from "node:crypto";
import { mkdirSync, readFileSync } from "node:fs";
import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  request,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { test, type Workspace } from "./fixtures";

const password = "LocalCRM!2026";
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/field-handoff") +
  "/screenshots";
mkdirSync(output, { recursive: true });
const number = () => "+9193" + randomInt(10000000, 99999999);
const local = (offset = 0) => {
  const d = new Date(Date.now() + offset);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};

test("rescheduling preserves the selected property while property lookup responses are delayed", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  const created = await workspace.api.post("/api/site-visits", {
    data: {
      lead_id: seed.lead.id,
      property_id: seed.property.id,
      assignee_id: workspace.user,
      starts_at: new Date(Date.now() + 3600000).toISOString(),
      duration_minutes: 60,
    },
  });
  expect(created.status()).toBe(201);
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  try {
    await login(page, workspace.phone);
    await page.goto("/app/site-visits");
    await page.route("**/api/properties**", async (route) => {
      await gate;
      await route.continue();
    });
    await page.getByRole("button", { name: "Reschedule", exact: true }).click();
    const form = page.getByRole("dialog", {
      name: "Reschedule site visit",
      exact: true,
    });
    await expect(form.getByLabel("Property", { exact: true })).toHaveValue(
      seed.property.id,
    );
    await form
      .getByLabel("Visit date & time", { exact: true })
      .fill(local(7200000));
    await form
      .getByRole("button", { name: "Save site visit", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    const saved = (await (await workspace.api.get("/api/site-visits")).json())
      .items[0];
    expect(saved.property_id).toBe(seed.property.id);
    expect(new Date(saved.starts_at).getTime()).toBeGreaterThan(
      Date.now() + 7000000,
    );
  } finally {
    release();
    await seed.callerApi.dispose();
  }
});
async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/(overview|field-work)/);
}
async function apiFor(phone: string) {
  const api = await request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  const response = await api.post("/api/auth/login", {
    data: { phone, password },
  });
  expect(response.ok()).toBeTruthy();
  const token = (await response.json()).access_token;
  await api.dispose();
  return request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    extraHTTPHeaders: {
      "X-Requested-With": "TalkoCRM",
      Authorization: "Bearer " + token,
    },
  });
}
async function member(workspace: Workspace, name: string, role: string) {
  const phone = number();
  const response = await workspace.api.post("/api/team", {
    data: { name, phone, role, password },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}
async function prepare(workspace: Workspace, field = true) {
  expect(
    (await workspace.api.post("/api/real-estate/setup")).ok(),
  ).toBeTruthy();
  const caller = await member(workspace, "QA Visit Caller", "telecaller");
  const executive = field
    ? await member(workspace, "QA Field Executive", "field_executive")
    : null;
  const callerApi = await apiFor(caller.phone);
  const leadResult = await callerApi.post("/api/leads", {
    data: {
      name: "QA Panipat Visit Client",
      phone: number(),
      city: "Panipat",
      notes:
        "Client wants a family apartment and confirmed financing questions.",
    },
  });
  expect(leadResult.status()).toBe(201);
  const propertyResult = await workspace.api.post("/api/properties", {
    data: {
      title: "QA Model Town Apartment",
      reference: "FIELD-" + Date.now(),
      property_type: "apartment",
      city: "Panipat",
      locality: "Model Town",
      address: "QA gate, Model Town, Panipat",
      price: "6500000",
      area_sqft: "1400",
      bedrooms: 3,
    },
  });
  expect(propertyResult.status()).toBe(201);
  return {
    caller,
    executive,
    callerApi,
    lead: await leadResult.json(),
    property: await propertyResult.json(),
  };
}
async function createApi(
  api: APIRequestContext,
  seed: Awaited<ReturnType<typeof prepare>>,
  offset = 3600000,
) {
  const response = await api.post("/api/field-work", {
    data: {
      lead_id: seed.lead.id,
      executive_id: seed.executive.id,
      property_id: seed.property.id,
      starts_at: new Date(Date.now() + offset).toISOString(),
      brief: "Confirmed client. Review financing and the three-bedroom layout.",
      meeting_point: "Model Town main gate",
      client_confirmed: true,
      request_id: crypto.randomUUID(),
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}
async function accessible(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(
    results.violations.filter((v) =>
      ["critical", "serious"].includes(v.impact || ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(
    await page.evaluate(
      () =>
        innerWidth >= 500 ||
        Array.from(
          document.querySelectorAll(
            ".field-work-filters input, .field-work-filters select",
          ),
        ).every((control) => control.getBoundingClientRect().width >= 250),
    ),
  ).toBeTruthy();
}

test("manager can review a field executive's work time while the executive cannot self-approve", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  const manager = await member(workspace, "QA Field Manager", "manager");
  const executiveApi = await apiFor(seed.executive.phone);
  try {
    const submitted = await executiveApi.post("/api/time-entries", {
      data: {
        day: new Date().toLocaleDateString("en-CA", {
          timeZone: "Asia/Kolkata",
        }),
        hours: "2",
        category: "other",
        description: "Visited the property with a client",
      },
    });
    expect(submitted.status()).toBe(201);
    const identity = (await submitted.json()).id;
    expect(
      (
        await executiveApi.post(`/api/time-entries/${identity}/review`, {
          data: { state: "approved", note: "Self approval attempt" },
        })
      ).status(),
    ).toBe(403);
    await login(page, manager.phone);
    await page.goto("/app/approvals");
    const row = page
      .getByRole("row")
      .filter({ hasText: "Visited the property with a client" });
    await row.getByRole("button", { name: "Review", exact: true }).click();
    const form = page.getByRole("dialog", {
      name: "Review the submission",
      exact: true,
    });
    await form.getByLabel("Decision", { exact: true }).selectOption("approved");
    await form
      .getByLabel("Review note", { exact: true })
      .fill("Verified the completed client visit");
    await form
      .getByRole("button", { name: "Record decision", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    await expect(row).toContainText("approved");
    const requests = await (await executiveApi.get("/api/time-entries")).json();
    expect(
      requests.find((entry: { id: string }) => entry.id === identity).state,
    ).toBe("approved");
  } finally {
    await executiveApi.dispose();
    await seed.callerApi.dispose();
  }
});

test("admin creates a field executive; caller hands off a visit; executive follows up and booking closes the case", async ({
  page,
  browser,
  workspace,
}) => {
  const seed = await prepare(workspace, false);
  const executivePhone = number();
  await login(page, workspace.phone);
  await page.goto("/app/team");
  await page
    .getByRole("button", { name: "Add team member", exact: true })
    .click();
  const team = page.getByRole("dialog");
  await team
    .getByLabel("Full name", { exact: true })
    .fill("QA Field Executive");
  await team.getByLabel("Login phone", { exact: true }).fill(executivePhone);
  await team.getByLabel("Initial password", { exact: true }).fill(password);
  await team
    .getByLabel("Workspace role", { exact: true })
    .selectOption("field_executive");
  await team.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(team).toHaveCount(0);
  seed.executive = (await (await workspace.api.get("/api/team")).json()).find(
    (u: { phone: string }) => u.phone === executivePhone,
  );
  const synced = await seed.callerApi.post("/api/phone-calls/sync", {
    data: {
      device_id: "qa-field-discussion",
      calls: [
        {
          device_call_id: "first-call",
          phone: seed.lead.phone,
          direction: "outgoing",
          result: "answered",
          started_at: new Date().toISOString(),
          duration: 32,
        },
      ],
    },
  });
  const call = (await synced.json()).entries[0];
  const uploaded = await seed.callerApi.post(
    `/api/leads/${seed.lead.id}/files`,
    {
      multipart: {
        phone_call_id: call.call_id,
        file: {
          name: "client-discussion.m4a",
          mimeType: "audio/mp4",
          buffer: readFileSync(
            "../backend/tests/fixtures/media/aac-3gp4-native-meta.m4a",
          ),
        },
      },
    },
  );
  expect(uploaded.status()).toBe(201);
  const callerContext = await browser.newContext(),
    callerPage = await callerContext.newPage();
  const executiveContext = await browser.newContext(),
    executivePage = await executiveContext.newPage();
  try {
    await login(callerPage, seed.caller.phone);
    await callerPage.goto("/app/leads/" + seed.lead.id);
    await callerPage
      .getByRole("button", { name: "Arrange visit & hand off", exact: true })
      .click();
    const form = callerPage.getByRole("dialog", {
      name: "Arrange visit & hand off",
      exact: true,
    });
    const selectedClient = form.getByRole("textbox", {
      name: "Client",
      exact: true,
    });
    await expect(selectedClient).toHaveValue(
      `${seed.lead.name} · ${seed.lead.phone}`,
    );
    await expect(selectedClient).toHaveAttribute("readonly", "");
    await expect(
      form.getByRole("searchbox", { name: "Search client", exact: true }),
    ).toHaveCount(0);
    await form
      .getByLabel("Field executive", { exact: true })
      .selectOption(seed.executive.id);
    await form
      .getByLabel("Property", { exact: true })
      .selectOption(seed.property.id);
    await form
      .getByLabel("Visit date & time", { exact: true })
      .fill(local(-60000));
    await form
      .getByLabel("Meeting point", { exact: true })
      .fill("Model Town main gate");
    await form
      .getByLabel("Client discussion & handoff brief", { exact: true })
      .fill(
        "Client confirmed a three-bedroom visit. Explain loan documents and parking.",
      );
    await form
      .getByRole("checkbox", {
        name: "The client agreed to this property visit and time",
        exact: true,
      })
      .check();
    await form
      .getByRole("button", { name: "Assign field executive", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    await expect(callerPage.locator(".field-work-card")).toContainText(
      "Awaiting acceptance",
    );
    await login(executivePage, executivePhone);
    await expect(executivePage).toHaveURL(/\/app\/field-work/);
    const card = executivePage.locator(".field-work-card");
    await expect(card).toContainText("QA Panipat Visit Client");
    await expect(card).toContainText("QA Visit Caller");
    await card
      .getByRole("button", { name: "Accept handoff", exact: true })
      .click();
    await expect(card).toContainText("Visit arranged");
    await card
      .getByRole("link", { name: "Open client history", exact: true })
      .click();
    await executivePage
      .getByRole("button", { name: "Calls", exact: true })
      .click();
    await expect(
      executivePage.locator(".call-card").filter({ hasText: "outgoing" }),
    ).toHaveCount(1);
    await executivePage
      .getByRole("button", { name: "Files", exact: true })
      .click();
    await expect(
      executivePage.getByText("client-discussion.m4a", { exact: true }),
    ).toBeVisible();
    await expect(
      executivePage.getByLabel("Remove client-discussion.m4a", { exact: true }),
    ).toHaveCount(0);
    await executivePage
      .locator(".field-work-card")
      .getByRole("button", { name: "Record visit outcome", exact: true })
      .click();
    const outcome = executivePage.getByRole("dialog", {
      name: "Record visit outcome & next step",
      exact: true,
    });
    await outcome
      .getByLabel("Client feedback & discussion", { exact: true })
      .fill(
        "Client attended and liked the layout. Loan documents are pending.",
      );
    await outcome
      .getByLabel("Next action", { exact: true })
      .fill("Confirm loan documents");
    await outcome
      .getByLabel("Follow-up date & time", { exact: true })
      .fill(local(86400000));
    await accessible(executivePage);
    await outcome
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(outcome).toHaveCount(0);
    await expect(executivePage.locator(".field-work-card")).toContainText(
      "Confirm loan documents",
    );
    await executivePage.goto("/app/tasks");
    await expect(
      executivePage.getByRole("button", {
        name: "Confirm loan documents",
        exact: true,
      }),
    ).toBeVisible();
    await executivePage
      .getByRole("link", { name: "Update field follow-up", exact: true })
      .click();
    await executivePage
      .getByRole("button", { name: "Record follow-up", exact: true })
      .click();
    const followup = executivePage.getByRole("dialog", {
      name: "Record client follow-up",
      exact: true,
    });
    await followup
      .getByLabel("What happens next?", { exact: true })
      .selectOption("ready_for_booking");
    await expect(
      followup.getByLabel("Follow-up date & time", { exact: true }),
    ).toHaveCount(0);
    await followup
      .getByLabel("Client feedback & discussion", { exact: true })
      .fill("Loan approved. Client is ready for booking review.");
    await followup
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(followup).toHaveCount(0);
    await executivePage.setViewportSize({ width: 390, height: 900 });
    await accessible(executivePage);
    await executivePage.screenshot({
      path: output + "/field-client-390.png",
      fullPage: true,
    });
    await callerPage.reload();
    await expect(callerPage.locator(".field-work-card")).toContainText(
      "Ready for booking",
    );
    await page.goto("/app/field-work");
    await page
      .getByRole("link", { name: "Create booking", exact: true })
      .click();
    const booking = page.getByRole("dialog", {
      name: "Create a property booking",
      exact: true,
    });
    await expect(
      booking.getByLabel("Buyer enquiry", { exact: true }),
    ).toHaveValue(seed.lead.id);
    await expect(booking.getByLabel("Property", { exact: true })).toHaveValue(
      seed.property.id,
    );
    await expect(
      booking.getByLabel("Booking agent", { exact: true }),
    ).toHaveValue(seed.executive.id);
    await booking
      .getByLabel("Booking reference", { exact: true })
      .fill("QA-FIELD-BOOK");
    await booking
      .getByLabel("Agreed deal value (₹)", { exact: true })
      .fill("6400000");
    await booking
      .getByRole("button", { name: "Reserve property", exact: true })
      .click();
    await expect(booking).toHaveCount(0);
    await page
      .getByRole("button", { name: "Update stage", exact: true })
      .click();
    const stage = page.getByRole("dialog", {
      name: "Update booking QA-FIELD-BOOK",
      exact: true,
    });
    await stage
      .getByLabel("Next stage", { exact: true })
      .selectOption("booked");
    await stage
      .getByRole("button", { name: "Save changes", exact: true })
      .click();
    await expect(stage).toHaveCount(0);
    await page.goto("/app/field-work");
    await page
      .getByLabel("Work status", { exact: true })
      .selectOption("closed");
    await expect(page.locator(".field-work-card")).toContainText(
      "Booking confirmed: QA-FIELD-BOOK",
    );
    await page.screenshot({
      path: output + "/field-booking-closed.png",
      fullPage: true,
    });
  } finally {
    await callerContext.close();
    await executiveContext.close();
    await seed.callerApi.dispose();
  }
});

test("lead profiles fix the handoff to the current client; the general field page still allows client search", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  const secondResult = await seed.callerApi.post("/api/leads", {
    data: { name: seed.lead.name, phone: number(), city: "Panipat" },
  });
  expect(secondResult.status()).toBe(201);
  const second = await secondResult.json();
  try {
    await login(page, seed.caller.phone);
    await page.setViewportSize({ width: 390, height: 900 });
    const form = page.getByRole("dialog", {
      name: "Arrange visit & hand off",
      exact: true,
    });
    for (const client of [seed.lead, second]) {
      await page.goto("/app/leads/" + client.id);
      await page
        .getByRole("button", { name: "Arrange visit & hand off", exact: true })
        .click();
      const selected = form.getByRole("textbox", {
        name: "Client",
        exact: true,
      });
      await expect(selected).toHaveValue(`${client.name} · ${client.phone}`);
      await expect(selected).toHaveAttribute("readonly", "");
      await expect(
        form.getByRole("searchbox", { name: "Search client", exact: true }),
      ).toHaveCount(0);
      await expect(
        form.getByRole("combobox", { name: "Client", exact: true }),
      ).toHaveCount(0);
      await accessible(page);
      await form.getByRole("button", { name: "Cancel", exact: true }).click();
      await expect(form).toHaveCount(0);
    }
    await page.goto("/app/field-work");
    await page
      .getByRole("button", { name: "Arrange visit & hand off", exact: true })
      .click();
    const clientChoice = form.getByRole("combobox", {
      name: "Client",
      exact: true,
    });
    await expect(clientChoice).toHaveValue("");
    await form
      .getByRole("searchbox", { name: "Search client", exact: true })
      .fill(second.phone);
    await clientChoice.selectOption(second.id);
    await expect(clientChoice).toHaveValue(second.id);
    await form
      .getByLabel("Field executive", { exact: true })
      .selectOption(seed.executive.id);
    await form
      .getByLabel("Property", { exact: true })
      .selectOption(seed.property.id);
    await form
      .getByLabel("Visit date & time", { exact: true })
      .fill(local(3600000));
    await form
      .getByLabel("Meeting point", { exact: true })
      .fill("Property main gate");
    await form
      .getByLabel("Client discussion & handoff brief", { exact: true })
      .fill("Client agreed to view this apartment.");
    await form.getByRole("checkbox", { name: /The client agreed/ }).check();
    await form
      .getByRole("button", { name: "Assign field executive", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    const handoffs = await (await seed.callerApi.get("/api/field-work")).json();
    expect(handoffs.total).toBe(1);
    expect(handoffs.items[0].lead_id).toBe(second.id);
    expect(
      (
        await (
          await seed.callerApi.get("/api/field-work?lead_id=" + seed.lead.id)
        ).json()
      ).total,
    ).toBe(0);
  } finally {
    await seed.callerApi.dispose();
  }
});

test("early attendance saves the actual past time and original schedule while future no-shows stay blocked", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  const executiveApi = await apiFor(seed.executive.phone);
  try {
    const handoff = await createApi(seed.callerApi, seed, 86400000);
    const accepted = await executiveApi.patch("/api/field-work/" + handoff.id, {
      data: { version: handoff.version, action: "accept" },
    });
    expect(accepted.ok()).toBeTruthy();
    await login(page, seed.executive.phone);
    await page.setViewportSize({ width: 390, height: 900 });
    await page.goto("/app/leads/" + seed.lead.id);
    await page
      .getByRole("button", { name: "Record visit outcome", exact: true })
      .click();
    const form = page.getByRole("dialog", {
      name: "Record visit outcome & next step",
      exact: true,
    });
    await expect(form.getByText(/Scheduled visit:/)).toBeVisible();
    await form
      .getByLabel("Visit result", { exact: true })
      .selectOption("no-show");
    await expect(
      form.getByRole("checkbox", {
        name: "Visit happened before the scheduled time",
        exact: true,
      }),
    ).toHaveCount(0);
    await form
      .getByLabel("What happens next?", { exact: true })
      .selectOption("closed");
    await form
      .getByLabel("Client feedback & discussion", { exact: true })
      .fill("Client visited early and wants financing details.");
    await form
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(form.getByRole("alert")).toContainText(
      "A no-show can only be recorded once the scheduled visit starts",
    );
    await form
      .getByLabel("Visit result", { exact: true })
      .selectOption("completed");
    await form
      .getByRole("checkbox", {
        name: "Visit happened before the scheduled time",
        exact: true,
      })
      .check();
    await form
      .getByLabel("Actual visit date & time", { exact: true })
      .fill(local(3600000));
    await form
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(form.getByRole("alert")).toContainText(
      "The actual early visit time must be in the past and before the scheduled visit",
    );
    const actual = local(-1800000);
    await form
      .getByLabel("Actual visit date & time", { exact: true })
      .fill(actual);
    await form
      .getByLabel("What happens next?", { exact: true })
      .selectOption("follow_up");
    await form
      .getByLabel("Next action", { exact: true })
      .fill("Discuss finance documents");
    await form
      .getByLabel("Follow-up date & time", { exact: true })
      .fill(local(7200000));
    await accessible(page);
    await page.screenshot({
      path: output + "/early-attendance-form-390.png",
      fullPage: true,
    });
    await form
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    await expect(page.locator(".field-work-card")).toContainText(
      "Client attended:",
    );
    const saved = (await (await executiveApi.get("/api/field-work")).json())
      .items[0];
    expect(new Date(saved.visit.starts_at).getTime()).toBe(
      new Date(handoff.visit.starts_at).getTime(),
    );
    expect(new Date(saved.visit.actual_started_at).toISOString()).toBe(
      new Date(actual).toISOString(),
    );
    expect(saved.visit.status).toBe("completed");
    expect(saved.status).toBe("follow_up");
    await page.reload();
    await expect(page.locator(".field-work-card")).toContainText(
      "Client attended:",
    );
    await page.goto("/app/site-visits");
    await expect(
      page.locator(".visit-card").filter({ hasText: seed.lead.name }),
    ).toContainText("Client attended:");
  } finally {
    await executiveApi.dispose();
    await seed.callerApi.dispose();
  }
});

test("handoff validation and temporary create failure preserve the caller's inputs; cancellation retains history", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  try {
    await login(page, seed.caller.phone);
    await page.goto("/app/leads/" + seed.lead.id);
    await page
      .getByRole("button", { name: "Arrange visit & hand off", exact: true })
      .click();
    const form = page.getByRole("dialog", {
      name: "Arrange visit & hand off",
      exact: true,
    });
    await form
      .getByLabel("Field executive", { exact: true })
      .selectOption(seed.executive.id);
    await form
      .getByLabel("Property", { exact: true })
      .selectOption(seed.property.id);
    await form
      .getByLabel("Visit date & time", { exact: true })
      .fill(local(3600000));
    await form
      .getByLabel("Meeting point", { exact: true })
      .fill("Meet at office reception");
    await form
      .getByLabel("Client discussion & handoff brief", { exact: true })
      .fill("Client has a confirmed budget and wants to view parking.");
    await form
      .getByRole("button", { name: "Assign field executive", exact: true })
      .click();
    await expect(form.getByRole("alert")).toContainText(
      "Confirm that the client agreed",
    );
    await form.getByRole("checkbox", { name: /The client agreed/ }).check();
    await page.route(
      "**/api/field-work",
      (route) =>
        route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({
            error: {
              code: "temporary",
              message: "Temporary handoff service failure",
            },
          }),
        }),
      { times: 1 },
    );
    await form
      .getByRole("button", { name: "Assign field executive", exact: true })
      .click();
    await expect(form.getByRole("alert")).toContainText(
      "Temporary handoff service failure",
    );
    await expect(form.getByLabel("Meeting point", { exact: true })).toHaveValue(
      "Meet at office reception",
    );
    await expect(
      form.getByRole("checkbox", { name: /The client agreed/ }),
    ).toBeChecked();
    await form
      .getByRole("button", { name: "Assign field executive", exact: true })
      .click();
    await expect(form).toHaveCount(0);
    await expect(
      page.getByRole("button", {
        name: "Arrange visit & hand off",
        exact: true,
      }),
    ).toHaveCount(0);
    expect(
      (await (await seed.callerApi.get("/api/field-work")).json()).total,
    ).toBe(1);
    await page
      .getByRole("button", { name: "Cancel field work", exact: true })
      .click();
    const cancel = page.getByRole("dialog", {
      name: "Cancel this field handoff",
      exact: true,
    });
    await cancel
      .getByLabel("Reason / instructions", { exact: true })
      .fill("Client changed travel plans. Coordinate a new date later.");
    await cancel
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(cancel).toHaveCount(0);
    await expect(page.locator(".field-work-card")).toContainText("Cancelled");
    await expect(
      page.getByRole("button", {
        name: "Arrange visit & hand off",
        exact: true,
      }),
    ).toBeVisible();
    const history = await (
      await seed.callerApi.get(`/api/leads/${seed.lead.id}/history`)
    ).json();
    expect(
      history.activity.some(
        (a: { action: string }) => a.action === "field_handoff_cancel",
      ),
    ).toBeTruthy();
  } finally {
    await seed.callerApi.dispose();
  }
});

test("reassignment requires resolution before deactivation and removes the previous executive's client access", async ({
  page,
  browser,
  workspace,
}) => {
  const seed = await prepare(workspace);
  const second = await member(
    workspace,
    "QA Replacement Executive",
    "field_executive",
  );
  const handoff = await createApi(seed.callerApi, seed);
  const context = await browser.newContext({
      viewport: { width: 390, height: 900 },
    }),
    old = await context.newPage();
  try {
    await login(old, seed.executive.phone);
    await expect(old.locator(".field-work-card")).toContainText(seed.lead.name);
    await login(page, workspace.phone);
    await page.goto("/app/team");
    const row = page.getByRole("row").filter({ hasText: seed.executive.name });
    await row.getByRole("button", { name: "Deactivate", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText(
      "Reassign or close this executive's active field work first",
    );
    await page.goto("/app/field-work");
    await page
      .getByRole("button", { name: "Change executive", exact: true })
      .click();
    const reassignment = page.getByRole("dialog", {
      name: "Change field executive",
      exact: true,
    });
    await reassignment
      .getByLabel("New field executive", { exact: true })
      .selectOption(second.id);
    await reassignment
      .getByLabel("Reason / instructions", { exact: true })
      .fill("Reassign because the first executive is unavailable.");
    await reassignment
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(reassignment).toHaveCount(0);
    await expect(page.locator(".field-work-card")).toContainText(second.name);
    await old
      .getByRole("button", { name: "Refresh work", exact: true })
      .click();
    await expect(old.locator(".field-work-card")).toHaveCount(0);
    await old.goto("/app/leads/" + seed.lead.id);
    await expect(old.getByRole("alert").first()).toContainText(
      "This lead is not available to you",
    );
    const stale = await workspace.api.patch("/api/field-work/" + handoff.id, {
      data: {
        version: handoff.version,
        action: "cancel",
        feedback: "Old form submitted",
      },
    });
    expect(stale.status()).toBe(409);
    await page.goto("/app/team");
    await row.getByRole("button", { name: "Deactivate", exact: true }).click();
    await expect(row).toContainText("inactive");
    await page.screenshot({
      path: output + "/field-reassigned.png",
      fullPage: true,
    });
  } finally {
    await context.close();
    await seed.callerApi.dispose();
  }
});

test("no-show requires a next step; another visit cancels the old follow-up and closed work stays readable", async ({
  page,
  workspace,
}) => {
  const seed = await prepare(workspace);
  await createApi(seed.callerApi, seed, -60000);
  try {
    await login(page, seed.executive.phone);
    await page
      .getByRole("button", { name: "Accept handoff", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Record visit outcome", exact: true })
      .click();
    const outcome = page.getByRole("dialog", {
      name: "Record visit outcome & next step",
      exact: true,
    });
    await outcome
      .getByLabel("Visit result", { exact: true })
      .selectOption("no-show");
    await outcome
      .getByLabel("What happens next?", { exact: true })
      .selectOption("ready_for_booking");
    await outcome
      .getByLabel("Client feedback & discussion", { exact: true })
      .fill("Client did not attend and asks for another date.");
    await outcome
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(outcome.getByRole("alert")).toContainText(
      "A no-show needs follow-up or closure",
    );
    await outcome
      .getByLabel("What happens next?", { exact: true })
      .selectOption("follow_up");
    await outcome
      .getByLabel("Next action", { exact: true })
      .fill("Agree a new visit date");
    await outcome
      .getByLabel("Follow-up date & time", { exact: true })
      .fill(local(7200000));
    await outcome
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(outcome).toHaveCount(0);
    await page
      .getByRole("button", {
        name: "Reschedule / arrange another visit",
        exact: true,
      })
      .click();
    const next = page.getByRole("dialog", {
      name: "Arrange the next visit",
      exact: true,
    });
    await expect(next.getByLabel("Property", { exact: true })).toHaveValue(
      seed.property.id,
    );
    await next
      .getByLabel("New visit date & time", { exact: true })
      .fill(local(-60000));
    await next
      .getByLabel("Reason / instructions", { exact: true })
      .fill("Client has arrived at the gate; arrange their visit now.");
    await next
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(next).toHaveCount(0);
    await expect(page.locator(".field-work-card")).toContainText(
      "Visit arranged",
    );
    await page
      .getByRole("button", { name: "Record visit outcome", exact: true })
      .click();
    const close = page.getByRole("dialog", {
      name: "Record visit outcome & next step",
      exact: true,
    });
    await close
      .getByLabel("What happens next?", { exact: true })
      .selectOption("closed");
    await close
      .getByLabel("Client feedback & discussion", { exact: true })
      .fill(
        "Client attended but decided against this location. Close field work.",
      );
    await close
      .getByRole("button", { name: "Save field update", exact: true })
      .click();
    await expect(close).toHaveCount(0);
    await page
      .getByLabel("Work status", { exact: true })
      .selectOption("closed");
    await expect(page.locator(".field-work-card")).toContainText(
      "Client attended but decided against this location",
    );
    await page.setViewportSize({ width: 390, height: 900 });
    await accessible(page);
    await page.screenshot({
      path: output + "/field-closed-390.png",
      fullPage: true,
    });
    await page
      .locator(".field-work-card")
      .getByRole("link", { name: "Open client history", exact: true })
      .click();
    await expect(
      page.getByRole("heading", {
        name: seed.lead.name,
        exact: true,
        level: 1,
      }),
    ).toBeVisible();
  } finally {
    await seed.callerApi.dispose();
  }
});
