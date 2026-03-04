import { defineConfig, devices } from '@playwright/test';

const useSystemChrome = !process.env.CI && process.env.PLAYWRIGHT_USE_SYSTEM_CHROME !== '0';

/**
 * Playwright E2E Testing Configuration
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  
  use: {
    baseURL: 'http://localhost:8502',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        ...(useSystemChrome ? { channel: 'chrome' } : {}),
      },
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:8502',
    reuseExistingServer: !process.env.CI,
  },
});
