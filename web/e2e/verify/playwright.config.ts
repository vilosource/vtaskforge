/**
 * Post-Deploy Verification Suite
 *
 * Runs journey-level tests against any deployed vtf environment.
 * No webServer — expects a running instance at VTF_BASE_URL.
 *
 * Usage:
 *   VTF_BASE_URL=https://vtf.viloforge.com \
 *   VTF_ADMIN_USER=admin \
 *   VTF_ADMIN_PASSWORD=<password> \
 *   VTF_API_TOKEN=<token> \
 *   npx playwright test --config=e2e/verify/playwright.config.ts
 */
import { defineConfig } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const baseURL = process.env.VTF_BASE_URL || 'http://localhost:8001';

export default defineConfig({
  testDir: './journeys',
  globalSetup: './global-setup.ts',
  globalTeardown: './global-teardown.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: '../../test-results/verify-report' }],
  ],
  use: {
    baseURL,
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    storageState: path.join(__dirname, 'auth-state.json'),
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
});
