/**
 * E2E tests for the console widget integration in vtf web.
 *
 * Tests the floating/docked/minimized terminal widget that embeds
 * vafi-console as an iframe across all entry points.
 *
 * Run: ./e2e/run-e2e.sh
 * Requires: kubectl port-forward for vtf-api (9999) and vafi-console (8765)
 */

import { test, expect, Page } from '@playwright/test';

const VTF_URL = process.env.VTF_BASE_URL || 'http://localhost:9999';
const CONSOLE_URL = process.env.CONSOLE_BASE_URL || 'http://localhost:8765';

async function login(page: Page) {
  await page.goto(`${VTF_URL}/login`);
  await page.fill('input[name="username"], input[type="text"]', 'admin');
  await page.fill('input[name="password"], input[type="password"]', 'admin');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/');
}

test.describe('Console Widget — Architect from Home', () => {
  test('Consult Architect button opens floating widget', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Click the Consult Architect button
    const btn = page.locator('button:has-text("Consult Architect")');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    // Widget should appear
    const widget = page.locator('[data-testid="console-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Should contain an iframe pointing to console with role=architect and embed=true
    const iframe = widget.locator('iframe');
    await expect(iframe).toBeVisible({ timeout: 5000 });
    const src = await iframe.getAttribute('src');
    expect(src).toContain('role=architect');
    expect(src).toContain('embed=true');

    // Title bar should show "Architect"
    await expect(widget.locator('text=Architect')).toBeVisible();

    // Should have layout control buttons
    await expect(widget.locator('button[title="Dock to side"]')).toBeVisible();
    await expect(widget.locator('button[title="Minimize"]')).toBeVisible();
    await expect(widget.locator('button[title="Close"]')).toBeVisible();
  });
});

test.describe('Console Widget — Architect from Project', () => {
  test('Plan with Architect opens widget with project context', async ({ page }) => {
    await login(page);

    // Navigate to first project
    await page.goto(`${VTF_URL}/projects`);
    await page.waitForSelector('a[href*="/projects/"]', { timeout: 10000 });
    await page.click('a[href*="/projects/"]:first-of-type');

    // Click Plan with Architect
    const btn = page.locator('button:has-text("Plan with Architect")');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    // Widget should appear with project in iframe URL
    const widget = page.locator('[data-testid="console-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    const iframe = widget.locator('iframe');
    const src = await iframe.getAttribute('src');
    expect(src).toContain('role=architect');
    expect(src).toContain('project=');
    expect(src).toContain('embed=true');
  });
});

test.describe('Console Widget — Debug on Task', () => {
  test('Debug button opens widget with pod and bash', async ({ page }) => {
    await login(page);

    // Find a doing task with pod_name via API
    const resp = await page.request.get(`${VTF_URL}/v1/tasks/?status=doing&page_size=1`);
    const data = await resp.json();
    const tasks = data.results || data;

    if (tasks.length === 0 || !tasks[0].claimed_by_pod_name) {
      test.skip(true, 'No doing task with pod_name — cannot test Debug');
      return;
    }

    const task = tasks[0];
    await page.goto(`${VTF_URL}/tasks/${task.id}`);

    // Debug button should be visible
    const btn = page.locator('button:has-text("Debug")');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    // Widget should open with pod connection
    const widget = page.locator('[data-testid="console-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    const iframe = widget.locator('iframe');
    const src = await iframe.getAttribute('src');
    expect(src).toContain(`pod=${task.claimed_by_pod_name}`);
    expect(src).toContain('command=bash');
    expect(src).toContain('embed=true');
  });

  test('Debug button hidden when no pod_name', async ({ page }) => {
    await login(page);

    // Find a doing task without pod_name
    const resp = await page.request.get(`${VTF_URL}/v1/tasks/?status=doing&page_size=10`);
    const data = await resp.json();
    const tasks = (data.results || data).filter((t: any) => !t.claimed_by_pod_name);

    if (tasks.length === 0) {
      test.skip(true, 'All doing tasks have pod_name — cannot test hidden Debug');
      return;
    }

    await page.goto(`${VTF_URL}/tasks/${tasks[0].id}`);
    await page.waitForLoadState('networkidle');

    // Debug button should NOT be visible
    const btn = page.locator('button:has-text("Debug")');
    await expect(btn).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Console Widget — Layout Switching', () => {
  test('floating to docked preserves iframe', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open widget
    const btn = page.locator('button:has-text("Consult Architect")');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    const widget = page.locator('[data-testid="console-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Verify iframe has console URL before docking
    const iframe = widget.locator('iframe');
    const srcBefore = await iframe.getAttribute('src');
    expect(srcBefore).toContain('role=architect');

    // Dock
    await widget.locator('button[title="Dock to side"]').click();

    // Widget should still be visible, now docked (right edge)
    await expect(widget).toBeVisible();
    const box = await widget.boundingBox();
    const viewport = page.viewportSize();
    if (box && viewport) {
      // Docked widget should be at the right edge
      expect(box.x + box.width).toBeCloseTo(viewport.width, -1);
    }

    // Iframe should still point to console with same params (auth code may differ)
    const srcAfter = await iframe.getAttribute('src');
    expect(srcAfter).toContain('role=architect');
    expect(srcAfter).toContain('embed=true');
  });

  test('minimize shows bar, restore brings widget back', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open widget
    await page.locator('button:has-text("Consult Architect")').click();
    const widget = page.locator('[data-testid="console-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Minimize
    await widget.locator('button[title="Minimize"]').click();

    // Minimized bar should appear
    const bar = page.locator('[data-testid="minimized-bar"]');
    await expect(bar).toBeVisible({ timeout: 3000 });
    await expect(bar.locator('text=Architect')).toBeVisible();

    // Click bar to restore
    await bar.click();

    // Widget should be back (floating container visible again)
    // The minimized bar should be gone and the full widget title bar should be visible
    await expect(widget.locator('button[title="Dock to side"]')).toBeVisible({ timeout: 3000 });
  });

  test('widget persists across page navigation', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open widget
    await page.locator('button:has-text("Consult Architect")').click();
    const widget = page.locator('[data-testid="console-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Minimize widget first so it doesn't cover the sidebar
    await widget.locator('button[title="Minimize"]').click();
    const bar = page.locator('[data-testid="minimized-bar"]');
    await expect(bar).toBeVisible({ timeout: 3000 });

    // Navigate to projects page
    await page.click('a[href="/projects"]');
    await page.waitForURL('**/projects');

    // Minimized bar should still be visible after navigation
    await expect(bar).toBeVisible();

    // Restore and verify widget comes back
    await bar.click();
    await expect(widget.locator('button[title="Dock to side"]')).toBeVisible({ timeout: 3000 });
  });

  test('close widget removes it', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open widget
    await page.locator('button:has-text("Consult Architect")').click();
    const widget = page.locator('[data-testid="console-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Close
    await widget.locator('button[title="Close"]').click();

    // Widget should be gone
    await expect(widget).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Console Widget — pod_name in API', () => {
  test('agent pod_name appears in task API response', async ({ page }) => {
    await login(page);

    // Check that the API returns claimed_by_pod_name field
    const resp = await page.request.get(`${VTF_URL}/v1/tasks/?status=doing&page_size=1`);
    const data = await resp.json();
    const tasks = data.results || data;

    if (tasks.length === 0) {
      test.skip(true, 'No doing tasks available');
      return;
    }

    // The field should exist (even if null)
    expect(tasks[0]).toHaveProperty('claimed_by_pod_name');
  });
});

test.describe('vafi-console — standalone check', () => {
  test('console serves frontend', async ({ page }) => {
    await page.goto(CONSOLE_URL);
    await page.waitForLoadState('domcontentloaded');
    // Console should load its UI
    await expect(page.locator('body')).not.toBeEmpty();
  });

  test('console embedded mode hides sidebar', async ({ page }) => {
    await page.goto(`${CONSOLE_URL}/?embed=true`);
    await page.waitForLoadState('domcontentloaded');
    const sidebar = page.locator('#sidebar');
    const isVisible = await sidebar.isVisible().catch(() => false);
    expect(isVisible).toBe(false);
  });
});
