/**
 * E2E tests for vafi-console integration in vtf web.
 *
 * Proves the delivered Phase 4 features work from a user's perspective:
 * 1. "Chat with Architect" button on home page opens console
 * 2. "Plan with Architect" button on project page opens console with project
 * 3. "Debug" button on running task opens console modal with terminal
 * 4. Terminal icon visible on running tasks in kanban
 *
 * Run: npx playwright test e2e/console-integration.spec.ts
 * Requires: kubectl port-forward for both vtf-api (9999) and vafi-console (8765)
 */

import { test, expect, Page } from '@playwright/test';

const VTF_URL = process.env.VTF_BASE_URL || 'http://localhost:9999';
const CONSOLE_URL = process.env.CONSOLE_BASE_URL || 'http://localhost:8765';

// Login helper — vtf requires session auth
async function login(page: Page) {
  await page.goto(`${VTF_URL}/login`);
  await page.fill('input[name="username"], input[type="text"]', 'admin');
  await page.fill('input[name="password"], input[type="password"]', 'admin');
  await page.click('button[type="submit"]');
  // Wait for redirect to home
  await page.waitForURL('**/');
}

test.describe('Home page — Chat with Architect', () => {
  test('button is visible in Quick Actions', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);
    await page.waitForSelector('text=Quick Actions');
    const btn = page.locator('text=Chat with Architect');
    await expect(btn).toBeVisible();
  });

  test('button opens console in new tab', async ({ page, context }) => {
    await login(page);
    await page.goto(VTF_URL);
    await page.waitForSelector('text=Chat with Architect');

    // Listen for new tab
    const [newPage] = await Promise.all([
      context.waitForEvent('page'),
      page.click('text=Chat with Architect'),
    ]);

    // New tab should be the console with role=architect
    await newPage.waitForLoadState('domcontentloaded');
    expect(newPage.url()).toContain('console');
    expect(newPage.url()).toContain('role=architect');
  });
});

test.describe('Project page — Plan with Architect', () => {
  test('button is visible on project dashboard', async ({ page }) => {
    await login(page);

    // Navigate to first project
    await page.goto(`${VTF_URL}/projects`);
    await page.waitForSelector('a[href*="/projects/"]');
    await page.click('a[href*="/projects/"]:first-of-type');
    await page.waitForSelector('text=Plan with Architect', { timeout: 10000 });

    const btn = page.locator('text=Plan with Architect');
    await expect(btn).toBeVisible();
  });

  test('button opens console with project context', async ({ page, context }) => {
    await login(page);

    await page.goto(`${VTF_URL}/projects`);
    await page.waitForSelector('a[href*="/projects/"]');
    await page.click('a[href*="/projects/"]:first-of-type');
    await page.waitForSelector('text=Plan with Architect', { timeout: 10000 });

    const [newPage] = await Promise.all([
      context.waitForEvent('page'),
      page.click('text=Plan with Architect'),
    ]);

    await newPage.waitForLoadState('domcontentloaded');
    expect(newPage.url()).toContain('console');
    expect(newPage.url()).toContain('role=architect');
    expect(newPage.url()).toContain('project=');
  });
});

test.describe('Task page — Debug button', () => {
  test('Debug button appears on tasks with status doing', async ({ page }) => {
    await login(page);

    // Find a task with status "doing" via API
    const resp = await page.request.get(`${VTF_URL}/v1/tasks/?status=doing&page_size=1`);
    const data = await resp.json();
    const tasks = data.results || data;

    if (tasks.length === 0) {
      test.skip(true, 'No tasks with status doing — cannot test Debug button');
      return;
    }

    const taskId = tasks[0].id;
    await page.goto(`${VTF_URL}/tasks/${taskId}`);
    await page.waitForSelector('text=Debug', { timeout: 10000 });

    const btn = page.locator('button:has-text("Debug")');
    await expect(btn).toBeVisible();
  });

  test('Debug button opens console modal with terminal', async ({ page }) => {
    await login(page);

    // Small delay to avoid socket issues from rapid sequential tests
    await page.waitForTimeout(500);
    const resp = await page.request.get(`${VTF_URL}/v1/tasks/?status=doing&page_size=1`);
    const data = await resp.json();
    const tasks = data.results || data;

    if (tasks.length === 0) {
      test.skip(true, 'No tasks with status doing — cannot test Debug modal');
      return;
    }

    const taskId = tasks[0].id;
    await page.goto(`${VTF_URL}/tasks/${taskId}`);
    await page.waitForSelector('button:has-text("Debug")', { timeout: 10000 });
    await page.click('button:has-text("Debug")');

    // Modal should appear with an iframe
    const modal = page.locator('[role="dialog"]');
    await expect(modal).toBeVisible({ timeout: 5000 });

    const iframe = modal.locator('iframe');
    await expect(iframe).toBeVisible({ timeout: 5000 });

    // Iframe src should point to console in embed mode
    const src = await iframe.getAttribute('src');
    expect(src).toContain('embed=true');
    expect(src).toContain('command=bash');
  });
});

test.describe('TaskCard — terminal icon on running tasks', () => {
  test('terminal icon visible on doing tasks in kanban', async ({ page }) => {
    await login(page);

    // Find a project with a workplan that has doing tasks
    const resp = await page.request.get(`${VTF_URL}/v1/tasks/?status=doing&page_size=1&expand=project`);
    const data = await resp.json();
    const tasks = data.results || data;

    if (tasks.length === 0) {
      test.skip(true, 'No doing tasks — cannot verify terminal icon');
      return;
    }

    // Navigate to the task's workplan board
    const task = tasks[0];
    if (!task.workplan || !task.milestone) {
      test.skip(true, 'Doing task has no workplan/milestone — cannot navigate to kanban');
      return;
    }

    await page.goto(`${VTF_URL}/projects/${task.project}/workplans/${task.workplan}/milestones/${task.milestone}`);
    await page.waitForSelector('[data-status="doing"]', { timeout: 10000 });

    // The doing task card should have a terminal icon
    const taskCard = page.locator(`[data-task-id="${task.id}"]`);
    const terminalIcon = taskCard.locator('text=terminal');
    await expect(terminalIcon).toBeVisible();
  });
});

test.describe('Console standalone — verify it loads', () => {
  test('console serves frontend and shows UI', async ({ page }) => {
    await page.goto(CONSOLE_URL);
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('text=vafi-console')).toBeVisible({ timeout: 10000 });
  });

  test('console embedded mode hides sidebar', async ({ page }) => {
    await page.goto(`${CONSOLE_URL}/?embed=true`);
    await page.waitForLoadState('domcontentloaded');
    // In embedded mode, sidebar should not be visible
    const sidebar = page.locator('#sidebar');
    // Either hidden or not present
    const isVisible = await sidebar.isVisible().catch(() => false);
    expect(isVisible).toBe(false);
  });
});
