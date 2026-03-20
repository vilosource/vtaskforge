import { test, expect } from '@playwright/test';

test.describe('Task detail modal', () => {
  test('clicking a task card opens the modal and closes with Escape', async ({ page }) => {
    // Navigate to a workplan board
    await page.goto('/');

    // Wait for loading
    await expect(page.getByText('Loading workplans...')).not.toBeVisible({ timeout: 10000 });

    const table = page.locator('table');
    if (!(await table.isVisible())) {
      // No workplans available — skip test
      test.skip();
      return;
    }

    // Navigate to the first workplan
    const firstLink = page.locator('table tbody tr:first-child td:first-child a');
    await firstLink.click();
    await expect(page).toHaveURL(/\/workplans\//);

    // Wait for board to load
    await expect(page.getByText('Loading board...')).not.toBeVisible({ timeout: 10000 });

    // Click the first task card
    const firstCard = page.locator('.task-card').first();
    if (!(await firstCard.isVisible())) {
      // No tasks on board — skip
      test.skip();
      return;
    }

    const taskTitle = await firstCard.locator('.task-card-title').textContent();
    await firstCard.click();

    // Modal should open with the task title
    const modal = page.getByRole('dialog', { name: 'Task detail' });
    await expect(modal).toBeVisible({ timeout: 5000 });

    if (taskTitle) {
      await expect(modal.getByText(taskTitle)).toBeVisible();
    }

    // Close with Escape key
    await page.keyboard.press('Escape');
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });

  test('modal close button dismisses the modal', async ({ page }) => {
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

    const firstCard = page.locator('.task-card').first();
    if (!(await firstCard.isVisible())) {
      test.skip();
      return;
    }

    await firstCard.click();

    const modal = page.getByRole('dialog', { name: 'Task detail' });
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Click the close button
    await modal.getByRole('button', { name: /close/i }).click();
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });
});
