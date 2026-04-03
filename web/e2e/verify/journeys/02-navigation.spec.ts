/**
 * Journey 2: Navigation
 *
 * Verifies all main pages load without errors via sidebar navigation.
 * Catches broken imports, missing chunks, and routing regressions.
 */
import { test, expect } from '@playwright/test';

test.describe('Navigation Journey', () => {
  let consoleErrors: string[];

  test.beforeEach(async ({ page }) => {
    consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        // Filter non-critical noise
        if (!text.includes('favicon') && !text.includes('manifest')) {
          consoleErrors.push(text);
        }
      }
    });
  });

  test('home page loads', async ({ page }) => {
    await page.goto('/');
    // Should show projects or workplans on home
    await page.waitForLoadState('domcontentloaded');
    expect(consoleErrors).toHaveLength(0);
  });

  test('projects page loads via sidebar', async ({ page }) => {
    await page.goto('/');
    const sidebar = page.locator('aside');
    await sidebar.getByRole('link', { name: 'Projects' }).click();

    await page.waitForURL('**/projects');
    await page.waitForLoadState('domcontentloaded');
    expect(consoleErrors).toHaveLength(0);
  });

  test('agents page loads via sidebar', async ({ page }) => {
    await page.goto('/');
    const sidebar = page.locator('aside');
    await sidebar.getByRole('link', { name: 'Agents' }).click();

    await page.waitForURL('**/agents');
    await page.waitForLoadState('domcontentloaded');
    expect(consoleErrors).toHaveLength(0);
  });

  test('settings page loads via sidebar', async ({ page }) => {
    await page.goto('/');
    const sidebar = page.locator('aside');
    await sidebar.getByRole('link', { name: 'Settings' }).click();

    await page.waitForURL('**/settings');
    await expect(page.getByRole('heading', { name: 'Profile' })).toBeVisible();
    expect(consoleErrors).toHaveLength(0);
  });
});
