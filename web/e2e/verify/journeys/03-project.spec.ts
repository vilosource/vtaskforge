/**
 * Journey 3: Project -> Workplan -> Kanban
 *
 * Verifies the primary user flow: browsing projects, drilling into
 * a workplan, and viewing the kanban board with tasks in correct columns.
 */
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const seedData = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'seed-data.json'), 'utf-8'),
);

test.describe('Project Journey', () => {
  test('project list shows verification project', async ({ page }) => {
    await page.goto('/projects');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText('_verify Verification Project')).toBeVisible();
  });

  test('project dashboard renders with workplan', async ({ page }) => {
    await page.goto(`/projects/${seedData.projectId}`);
    await page.waitForLoadState('domcontentloaded');

    // Dashboard should show the project name
    await expect(page.getByRole('heading', { name: '_verify Verification Project' })).toBeVisible();
    // Workplan should be listed
    await expect(page.getByText('_verify Workplan')).toBeVisible();
  });

  test('workplan detail shows milestone', async ({ page }) => {
    await page.goto(`/projects/${seedData.projectId}/workplans/${seedData.workplanId}`);
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText('_verify Milestone')).toBeVisible();
  });

  test('kanban board renders with correct columns', async ({ page }) => {
    await page.goto(
      `/projects/${seedData.projectId}/workplans/${seedData.workplanId}/milestones/${seedData.milestoneId}`,
    );
    await page.waitForLoadState('domcontentloaded');

    // Verify kanban columns
    await expect(page.locator('[data-column="draft"]')).toBeVisible();
    await expect(page.locator('[data-column="ready"]')).toBeVisible();
    await expect(page.locator('[data-column="in-progress"]')).toBeVisible();
    await expect(page.locator('[data-column="done"]')).toBeVisible();
  });

  test('seeded tasks are visible on the board', async ({ page }) => {
    await page.goto(
      `/projects/${seedData.projectId}/workplans/${seedData.workplanId}/milestones/${seedData.milestoneId}`,
    );
    await page.waitForLoadState('domcontentloaded');

    // Verify each seeded task appears somewhere on the board.
    // We don't assert exact column placement because active agents on dev/prod
    // may claim or transition tasks between seed and test execution.
    for (const [key, taskId] of Object.entries(seedData.taskIds)) {
      const card = page.locator(`[data-task-id="${taskId}"]`);
      await expect(card).toBeVisible({ timeout: 15_000 });
    }
  });

  test('breadcrumb navigation works', async ({ page }) => {
    await page.goto(
      `/projects/${seedData.projectId}/workplans/${seedData.workplanId}/milestones/${seedData.milestoneId}`,
    );
    await page.waitForLoadState('domcontentloaded');

    const breadcrumb = page.getByRole('navigation', { name: 'Breadcrumb' });
    await expect(breadcrumb).toBeVisible();

    // Click project link in breadcrumb to go back
    await breadcrumb.getByText('_verify Verification Project').click();
    await page.waitForURL(`**/projects/${seedData.projectId}`);
  });
});
