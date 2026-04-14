import { defineConfig } from '@playwright/test';

/**
 * Playwright config for chat widget E2E tests.
 * Runs against a live VTF deployment (no local webServer).
 *
 * Usage:
 *   VTF_BASE_URL=http://localhost:9999 npx playwright test --config=chat-e2e.config.ts
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: 'chat-widget.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: 0,
  use: {
    baseURL: process.env.VTF_BASE_URL || 'http://localhost:9999',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
