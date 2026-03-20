import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  baseURL: 'http://localhost:3000',
  use: {
    headless: true,
  },
  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: true,
  },
});
