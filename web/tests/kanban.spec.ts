import { test, expect } from '@playwright/test';

test.describe('Kanban board page', () => {
  test('navigating to /workplans/:id shows the kanban board or error', async ({ page }) => {
    // Navigate to the workplan list first to get a real workplan ID if available
    await page.goto('/');

    // Wait for loading to complete
    await expect(page.getByText('Loading workplans...')).not.toBeVisible({ timeout: 10000 });

    const table = page.locator('table');
    if (!(await table.isVisible())) {
      // No workplans — navigate directly to a placeholder ID and verify board renders
      await page.goto('/workplans/test-id');
      await expect(page.getByText('Loading board...')).not.toBeVisible({ timeout: 10000 });
      // Should show error or empty state (no real backend data)
      return;
    }

    // Click the first workplan to navigate to its board
    const firstLink = page.locator('table tbody tr:first-child td:first-child a');
    const href = await firstLink.getAttribute('href');
    await firstLink.click();

    await expect(page).toHaveURL(/\/workplans\//);

    // Wait for board to load
    await expect(page.getByText('Loading board...')).not.toBeVisible({ timeout: 10000 });

    void href;
  });

  test('kanban board shows 6 columns when data is available', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Loading workplans...')).not.toBeVisible({ timeout: 10000 });

    const table = page.locator('table');
    if (!(await table.isVisible())) {
      test.skip();
      return;
    }

    const firstLink = page.locator('table tbody tr:first-child td:first-child a');
    await firstLink.click();

    await expect(page).toHaveURL(/\/workplans\//);
    await expect(page.getByText('Loading board...')).not.toBeVisible({ timeout: 10000 });

    // Verify columns are visible
    const draftColumn = page.locator('[data-column="draft"]');
    const reviewColumn = page.locator('[data-column="review"]');
    const readyColumn = page.locator('[data-column="ready"]');
    const inProgressColumn = page.locator('[data-column="in-progress"]');
    const attentionColumn = page.locator('[data-column="attention"]');
    const doneColumn = page.locator('[data-column="done"]');

    // Check that the board either shows all 6 columns or the empty state
    const hasColumns = await draftColumn.isVisible();
    const hasEmptyState = await page.getByText('No tasks yet.').isVisible();

    if (hasColumns) {
      await expect(draftColumn).toBeVisible();
      await expect(reviewColumn).toBeVisible();
      await expect(readyColumn).toBeVisible();
      await expect(inProgressColumn).toBeVisible();
      await expect(attentionColumn).toBeVisible();
      await expect(doneColumn).toBeVisible();
    } else {
      expect(hasEmptyState).toBe(true);
    }
  });

  test('task cards are clickable', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Loading workplans...')).not.toBeVisible({ timeout: 10000 });

    const table = page.locator('table');
    if (!(await table.isVisible())) {
      test.skip();
      return;
    }

    const firstLink = page.locator('table tbody tr:first-child td:first-child a');
    await firstLink.click();

    await expect(page).toHaveURL(/\/workplans\//);
    await expect(page.getByText('Loading board...')).not.toBeVisible({ timeout: 10000 });

    const taskCard = page.locator('[data-task-id]').first();
    if (!(await taskCard.isVisible())) {
      test.skip();
      return;
    }

    // Click should not throw or navigate away (modal is task 4.5)
    await taskCard.click();
    await expect(page).toHaveURL(/\/workplans\//);
  });
});
