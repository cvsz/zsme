import { defineConfig, devices } from '@playwright/test';

const playwrightPort = process.env.PLAYWRIGHT_PORT ?? '3100';
const playwrightCommand = process.env.PLAYWRIGHT_COMMAND ?? `npm run dev -- --hostname 127.0.0.1 --port ${playwrightPort}`;

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${playwrightPort}`,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: playwrightCommand,
    env: { NEXT_PUBLIC_API_BASE_URL: '' },
    url: `http://127.0.0.1:${playwrightPort}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
