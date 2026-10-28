import { defineConfig } from "@playwright/test";
const artifacts = process.env.E2E_ARTIFACT_DIR || "../artifacts/redesign";
export default defineConfig({
  testDir: "./tests",
  outputDir: artifacts + "/test-results",
  timeout: 45000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    [
      "html",
      {
        open: "never",
        outputFolder: artifacts + "/playwright-report",
      },
    ],
    ["json", { outputFile: artifacts + "/browser-tests.json" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    browserName: (process.env.E2E_BROWSER || "chromium") as
      "chromium" | "firefox" | "webkit",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
