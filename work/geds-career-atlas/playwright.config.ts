import { defineConfig, devices } from "@playwright/test"
import path from "node:path"

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8780",
    channel: "chrome",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "desktop-chrome", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "py -m geds_crawler.career_cli serve --master-db ../../outputs/master/geds-master.sqlite --frontend-dir ../geds-career-atlas/dist --host 127.0.0.1 --port 8780",
    cwd: path.resolve("../geds-crawler"),
    env: { PYTHONPATH: path.resolve("../geds-crawler/src") },
    url: "http://127.0.0.1:8780/api/meta",
    reuseExistingServer: true,
    timeout: 30_000,
  },
})
