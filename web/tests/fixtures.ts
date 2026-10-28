import {
  test as base,
  expect,
  request,
  type APIRequestContext,
} from "@playwright/test";
import { randomInt } from "node:crypto";
const password = "LocalCRM!2026";
const baseURL = process.env.E2E_BASE_URL || "http://localhost:5173";
const phone = () => "+9197" + String(randomInt(10000000, 99999999));

// Only tests that request this fixture create a separate temporary workspace.
export interface Workspace {
  api: APIRequestContext;
  phone: string;
  user: string;
  name: string;
}
export const test = base.extend<{ workspace: Workspace }>({
  workspace: async ({ browserName }, provide) => {
    const owner = await request.newContext({
      baseURL,
      extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
    });
    const auth = await owner.post("/api/auth/login", {
      data: { phone: "+919900000001", password },
    });
    expect(auth.ok(), await auth.text()).toBeTruthy();
    const token = (await auth.json()).access_token;
    const number = phone(),
      name =
        "Final QA " + browserName + " " + Date.now() + " " + randomInt(9999);
    const created = await owner.post("/api/platform/organizations", {
      headers: { Authorization: "Bearer " + token },
      data: {
        name,
        admin: {
          name: "QA Administrator",
          phone: number,
          password,
          role: "admin",
        },
      },
    });
    expect(created.status(), await created.text()).toBe(201);
    const org = await created.json();
    const api = await request.newContext({
      baseURL,
      extraHTTPHeaders: { "X-Requested-With": "TalkoCRM" },
    });
    const signed = await api.post("/api/auth/login", {
      data: { phone: number, password },
    });
    const session = await signed.json();
    await api.dispose();
    const authorized = await request.newContext({
      baseURL,
      extraHTTPHeaders: {
        "X-Requested-With": "TalkoCRM",
        Authorization: "Bearer " + session.access_token,
      },
    });
    try {
      await provide({
        api: authorized,
        phone: number,
        user: org.admin.id,
        name,
      });
    } finally {
      await authorized.dispose();
      try {
        const cleanup = await owner.delete(
          "/api/platform/organizations/" + org.organization.id,
          {
            headers: { Authorization: "Bearer " + token },
            params: { confirmation: name },
          },
        );
        expect(cleanup.ok(), await cleanup.text()).toBeTruthy();
      } finally {
        await owner.dispose();
      }
    }
  },
});
