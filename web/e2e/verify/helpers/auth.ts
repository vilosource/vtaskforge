/**
 * Authentication helper for verification tests.
 *
 * Logs in via the UI and saves storageState for reuse across all journeys.
 */
import { chromium, type BrowserContext, type Page } from '@playwright/test';

const BASE_URL = process.env.VTF_BASE_URL || 'http://localhost:8001';
const ADMIN_USER = process.env.VTF_ADMIN_USER || 'admin';
const ADMIN_PASSWORD = process.env.VTF_ADMIN_PASSWORD || 'admin';

export async function createAuthState(storageStatePath: string): Promise<void> {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto(`${BASE_URL}/login`);
  await page.getByRole('textbox', { name: 'Username' }).fill(ADMIN_USER);
  await page.getByRole('textbox', { name: 'Password' }).fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();

  // Wait for redirect away from login — use waitForLoadState instead of
  // waitForURL with predicate, which can miss fast navigations
  await page.waitForTimeout(3000);
  await page.waitForLoadState('domcontentloaded');

  // Verify we actually left the login page
  if (page.url().includes('/login')) {
    throw new Error(`Login failed — still on ${page.url()}`);
  }

  await context.storageState({ path: storageStatePath });
  await browser.close();
}

export async function loginAs(
  browser: { newContext: () => Promise<BrowserContext> },
  username: string,
  password: string,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`${BASE_URL}/login`);
  await page.getByRole('textbox', { name: 'Username' }).fill(username);
  await page.getByRole('textbox', { name: 'Password' }).fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15_000 });
  await page.waitForTimeout(2000);
  return { context, page };
}
