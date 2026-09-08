import { defineConfig, devices } from "@playwright/test";

// Allow pointing at a preinstalled Chromium (e.g. in a sandbox where the bundled build differs).
// CI leaves this unset and uses `npx playwright install --with-deps chromium`.
const executablePath = process.env.PW_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:8123",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(executablePath ? { launchOptions: { executablePath } } : {}),
      },
    },
  ],
  webServer: {
    command: "bash ../scripts/e2e-server.sh",
    url: "http://localhost:8123/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
