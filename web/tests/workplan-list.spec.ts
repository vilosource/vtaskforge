import { test, expect } from '@playwright/test';

test.describe('Workplan list page', () => {
  test('shows workplan list or empty state at /', async ({ page }) => {
    await page.goto('/');

    // Wait for loading to complete (loading text should disappear)
    await expect(page.getByText('Loading workplans...')).not.toBeVisible({ timeout: 10000 });

    // Either we see workplans or the empty state
    const hasWorkplans = await page.locator('table').isVisible();
    const hasEmptyState = await page.getByText('No workplans yet.').isVisible();

    expect(hasWorkplans || hasEmptyState).toBe(true);
  });

  test('clicking a workplan navigates to /workplans/:id', async ({ page }) => {
    await page.goto('/');

    // Wait for data to load
    await expect(page.getByText('Loading workplans...')).not.toBeVisible({ timeout: 10000 });

    // Skip if no workplans
    const table = page.locator('table');
    if (!(await table.isVisible())) {
      test.skip();
      return;
    }

    // Click the first workplan link
    const firstLink = page.locator('table tbody tr:first-child td:first-child a');
    const href = await firstLink.getAttribute('href');
    await firstLink.click();

    // Verify we navigated to a workplan detail page
    expect(href).toMatch(/^\/workplans\//);
    await expect(page).toHaveURL(/\/workplans\//);
  });
});
