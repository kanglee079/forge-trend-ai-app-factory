import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./apps/dashboard/e2e",
  timeout: 10 * 60 * 1000,
  expect: { timeout: 30 * 1000 },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  outputDir: "test-results",
  reporter: [["list"], ["html", { open: "never" }]],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
