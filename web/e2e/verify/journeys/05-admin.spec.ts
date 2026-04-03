/**
 * Journey 5: Admin Pages
 *
 * Verifies admin pages load and are properly restricted.
 * Uses different API endpoints and permissions than the main UI.
 */
import { test, expect } from '@playwright/test';

test.describe('Admin Journey', () => {
  test('sidebar shows admin section for staff', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    const sidebar = page.locator('aside');
    await expect(sidebar.getByText('Admin', { exact: true })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Users' })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Locks' })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Channels' })).toBeVisible();
  });

  test('users page renders with user table', async ({ page }) => {
    await page.goto('/manage/users');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();
    await expect(page.locator('table')).toBeVisible();
    // At minimum, admin user should appear
    await expect(page.locator('table').getByText('admin')).toBeVisible();
  });

  test('users page search works', async ({ page }) => {
    await page.goto('/manage/users');
    await page.waitForLoadState('domcontentloaded');

    await page.getByPlaceholder('Search users...').fill('admin');
    await page.waitForTimeout(1500);
    await expect(page.locator('table').getByText('admin')).toBeVisible();
  });

  test('locks page renders', async ({ page }) => {
    await page.goto('/manage/locks');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('heading', { name: 'Agent Locks' })).toBeVisible();
  });

  test('channel mappings page renders', async ({ page }) => {
    await page.goto('/manage/channel-mappings');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('heading', { name: 'Channel Mappings' })).toBeVisible();
  });
});
