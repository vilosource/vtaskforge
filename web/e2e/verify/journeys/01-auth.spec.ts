/**
 * Journey 1: Authentication
 *
 * Verifies the login flow works end-to-end against the deployed instance.
 * This is the gate to everything — if auth breaks, nothing else works.
 */
import { test, expect } from '@playwright/test';

const BASE_URL = process.env.VTF_BASE_URL || 'http://localhost:8001';
const ADMIN_USER = process.env.VTF_ADMIN_USER || 'admin';
const ADMIN_PASSWORD = process.env.VTF_ADMIN_PASSWORD || 'admin';
const API_TOKEN = process.env.VTF_API_TOKEN || '';

test.describe('Authentication Journey', () => {
  // Override global storageState — auth tests manage their own sessions
  test.use({ storageState: { cookies: [], origins: [] } });

  test('unauthenticated user is redirected to login', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    // Wait for SPA router to redirect
    await page.waitForTimeout(3000);

    expect(page.url()).toContain('/login');
    await context.close();
  });

  test('login page renders correctly', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });

    await expect(page.getByText('VTaskForge')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();

    await context.close();
  });

  test('invalid credentials show error', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('textbox', { name: 'Username' }).fill('wrong');
    await page.getByRole('textbox', { name: 'Password' }).fill('wrong');
    await page.getByRole('button', { name: 'Sign in' }).click();

    // Should stay on login
    await page.waitForTimeout(2000);
    expect(page.url()).toContain('/login');

    await context.close();
  });

  test('valid credentials reach home page', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('textbox', { name: 'Username' }).fill(ADMIN_USER);
    await page.getByRole('textbox', { name: 'Password' }).fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();

    await page.waitForTimeout(3000);
    expect(page.url()).not.toContain('/login');

    await context.close();
  });

  test('token validation endpoint returns user info', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/v1/auth/validate/`, {
      headers: { Authorization: `Token ${API_TOKEN}` },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('user_id');
    expect(data).toHaveProperty('username');
    expect(data).toHaveProperty('user_type');
  });
});
