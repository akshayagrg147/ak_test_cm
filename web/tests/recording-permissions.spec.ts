import { randomInt } from "node:crypto";
import { mkdirSync, readFileSync } from "node:fs";
import { expect, request, type Page } from "@playwright/test";
import { test } from "./fixtures";

const password = "LocalCRM!2026";
const output =
  (process.env.E2E_ARTIFACT_DIR || "../artifacts/recording-permissions") +
  "/screenshots";
mkdirSync(output, { recursive: true });
const recording = readFileSync(
  "../backend/tests/fixtures/media/aac-3gp4-native-meta.m4a",
);
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGMUCTjBAAJMYJKBgQEAEkIBMLmziVsAAAAASUVORK5CYII=",
  "base64",
);

async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByLabel("Phone number", { exact: false }).fill(phone);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/app\/overview/);
}

test("telecaller recordings have no remove action, API rejects deletion, playback works and admin can remove", async ({
  page,
  workspace,
}) => {
  const phone = "+9196" + randomInt(10000000, 99999999);
  const member = await workspace.api.post("/api/team", {
    data: { name: "QA Recording Caller", phone, password, role: "telecaller" },
  });
  expect(member.status()).toBe(201);
  const caller = await request.newContext({
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
  });
  try {
    const signed = await caller.post("/api/auth/login", {
      data: { phone, password },
    });
    expect(signed.ok()).toBeTruthy();
    const headers = {
      Authorization: "Bearer " + (await signed.json()).access_token,
    };
    const leadResult = await caller.post("/api/leads", {
      headers,
      data: { name: "QA Recording Customer", phone: "+919876540461" },
    });
    expect(leadResult.status()).toBe(201);
    const lead = await leadResult.json();
    const synced = await caller.post("/api/phone-calls/sync", {
      headers,
      data: {
        device_id: "qa-recording-permissions",
        calls: [
          {
            device_call_id: "qa-call-1",
            phone: lead.phone,
            direction: "outgoing",
            result: "answered",
            started_at: new Date().toISOString(),
            duration: 12,
          },
        ],
      },
    });
    expect(synced.ok()).toBeTruthy();
    const call = (await synced.json()).entries[0];
    const uploaded = await caller.post(`/api/leads/${lead.id}/files`, {
      headers,
      multipart: {
        phone_call_id: call.call_id,
        file: {
          name: "call-recording.m4a",
          mimeType: "audio/mp4",
          buffer: recording,
        },
      },
    });
    expect(uploaded.status()).toBe(201);
    const attachment = await uploaded.json();
    await login(page, phone);
    await page.goto("/app/leads/" + lead.id);
    await page.getByRole("button", { name: "Files", exact: true }).click();
    await page
      .locator("input[type=file]")
      .setInputFiles({
        name: "loose-audio.m4a",
        mimeType: "audio/mp4",
        buffer: recording,
      });
    await expect(
      page.getByText("loose-audio.m4a", { exact: true }),
    ).toBeVisible();
    await page
      .locator("input[type=file]")
      .setInputFiles({
        name: "ordinary-photo.png",
        mimeType: "image/png",
        buffer: png,
      });
    await expect(
      page.getByLabel("Remove ordinary-photo.png", { exact: true }),
    ).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Files", exact: true }).click();
    for (const name of ["call-recording.m4a", "loose-audio.m4a"]) {
      await expect(page.getByText(name, { exact: true })).toBeVisible();
      await expect(
        page.getByLabel("Remove " + name, { exact: true }),
      ).toHaveCount(0);
    }
    const denied = await caller.delete("/api/files/" + attachment.id, {
      headers,
    });
    expect(denied.status()).toBe(403);
    expect((await denied.json()).error.code).toBe("recording_delete_forbidden");
    const row = page
      .locator(".file-row")
      .filter({ hasText: "call-recording.m4a" });
    await row
      .getByRole("button", { name: "Play recording", exact: false })
      .click();
    const audio = row.locator("audio");
    await expect(audio).toBeVisible();
    await audio.evaluate((element: HTMLAudioElement) => element.load());
    await expect
      .poll(() =>
        audio.evaluate((element: HTMLAudioElement) => element.duration),
      )
      .toBeGreaterThan(0);
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByLabel("Download call-recording.m4a", { exact: true }).click(),
    ]);
    const stream = await download.createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream!) chunks.push(chunk);
    expect(Buffer.concat(chunks)).toEqual(recording);
    await page.getByLabel("Remove ordinary-photo.png", { exact: true }).click();
    await expect(
      page.getByText("ordinary-photo.png", { exact: true }),
    ).toHaveCount(0);
    await page.screenshot({
      path: output + "/telecaller-recordings.png",
      fullPage: true,
    });
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await login(page, workspace.phone);
    await page.goto("/app/leads/" + lead.id);
    await page.getByRole("button", { name: "Files", exact: true }).click();
    await expect(
      page.getByLabel("Remove call-recording.m4a", { exact: true }),
    ).toBeVisible();
    await page.getByLabel("Remove call-recording.m4a", { exact: true }).click();
    await expect(
      page.getByText("call-recording.m4a", { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText("loose-audio.m4a", { exact: true }),
    ).toBeVisible();
    const savedCall = (
      await (await caller.get("/api/phone-calls", { headers })).json()
    ).items[0];
    expect(savedCall.recording_state).toBe("unavailable");
  } finally {
    await caller.dispose();
  }
});
