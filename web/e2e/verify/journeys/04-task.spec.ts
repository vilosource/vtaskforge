/**
 * Journey 4: Task Detail
 *
 * Verifies task detail modal and full task page render correctly.
 * This is where operators and agents get implementation specs.
 */
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const seedData = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'seed-data.json'), 'utf-8'),
);

test.describe('Task Detail Journey', () => {
  test('clicking a task card opens detail modal', async ({ page }) => {
    await page.goto(
      `/projects/${seedData.projectId}/workplans/${seedData.workplanId}/milestones/${seedData.milestoneId}`,
    );
    await page.waitForLoadState('domcontentloaded');

    // Click the draft task card
    const taskCard = page.locator(`[data-task-id="${seedData.taskIds.draft}"]`);
    await expect(taskCard).toBeVisible();
    await taskCard.click();

    // Modal should open
    const modal = page.getByRole('dialog', { name: 'Task detail' });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal.getByText('_verify Draft Task')).toBeVisible();
  });

  test('modal closes with Escape', async ({ page }) => {
    await page.goto(
      `/projects/${seedData.projectId}/workplans/${seedData.workplanId}/milestones/${seedData.milestoneId}`,
    );
    await page.waitForLoadState('domcontentloaded');

    const taskCard = page.locator(`[data-task-id="${seedData.taskIds.draft}"]`);
    await taskCard.click();

    const modal = page.getByRole('dialog', { name: 'Task detail' });
    await expect(modal).toBeVisible({ timeout: 5000 });

    await page.keyboard.press('Escape');
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });

  test('full task page renders via direct URL', async ({ page }) => {
    await page.goto(`/tasks/${seedData.taskIds.draft}`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByRole('heading', { name: '_verify Draft Task' })).toBeVisible();
  });
});
