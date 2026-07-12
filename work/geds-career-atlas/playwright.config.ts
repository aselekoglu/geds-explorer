import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  globalSetup:"./tests/e2e/global-setup.ts",
  use: {
    baseURL: "http://127.0.0.1:8780",
    channel: "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "desktop-chrome", use: { ...devices["Desktop Chrome"] } }],
})
