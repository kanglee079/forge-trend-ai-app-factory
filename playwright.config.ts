import { defineConfig, devices } from "@playwright/test";

const apiBaseURL = process.env.PLAYWRIGHT_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const dashboardBaseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3100";

export default defineConfig({
  testDir: "./apps/dashboard/e2e",
  timeout: 10 * 60 * 1000,
  expect: { timeout: 30 * 1000 },
  use: {
    baseURL: dashboardBaseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  outputDir: "test-results",
  reporter: [["list"], ["html", { open: "never" }]],
  webServer: {
    command: "pnpm --filter @forge/dashboard exec next dev --hostname localhost --port 3100",
    url: `${dashboardBaseURL}/factory`,
    timeout: 120 * 1000,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
    env: {
      ...process.env,
      NEXT_PUBLIC_API_BASE_URL: apiBaseURL,
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
