/**
 * E2E tests for the chat widget integration in vtf web.
 *
 * Tests the floating/docked/minimized chat widget that connects to
 * the bridge API for AI-assisted project conversations.
 *
 * Run: npx playwright test e2e/chat-widget.spec.ts
 * Requires: kubectl port-forward for vtf-api (9999) and bridge API
 */

import { test, expect, Page } from '@playwright/test';

const VTF_URL = process.env.VTF_BASE_URL || 'http://localhost:9999';

async function login(page: Page) {
  await page.goto(`${VTF_URL}/login`);
  await page.fill('input[name="username"], input[type="text"]', 'admin');
  await page.fill('input[name="password"], input[type="password"]', 'admin');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/');
}

test.describe('Chat Widget — from Home', () => {
  test('Chat with Architect button opens floating chat widget', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    const btn = page.locator('button:has-text("Chat with Architect")');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Title bar should be present
    await expect(page.locator('[data-testid="chat-title-bar"]')).toBeVisible();

    // Chat input should be present
    await expect(page.locator('[data-testid="chat-input"]')).toBeVisible();

    // Should have layout control buttons
    await expect(widget.locator('button[title="Dock to side"]')).toBeVisible();
    await expect(widget.locator('button[title="Minimize"]')).toBeVisible();
    await expect(widget.locator('button[title="Close"]')).toBeVisible();
  });
});

test.describe('Chat Widget — from Project', () => {
  test('Chat with Architect opens with project context', async ({ page }) => {
    await login(page);

    // Navigate to first project
    await page.goto(`${VTF_URL}/projects`);
    await page.waitForSelector('a[href*="/projects/"]', { timeout: 10000 });
    await page.click('a[href*="/projects/"]:first-of-type');

    // Click Chat with Architect
    const btn = page.locator('button:has-text("Chat with Architect")');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    // Widget should appear with project name in title
    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid="chat-title-bar"]')).toBeVisible();
  });
});

test.describe('Chat Widget — Layout Switching', () => {
  test('floating to docked preserves state', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open widget
    const btn = page.locator('button:has-text("Chat with Architect")');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();

    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Dock
    await widget.locator('button[title="Dock to side"]').click();

    // Widget should still be visible
    await expect(widget).toBeVisible();

    // Should now show Float button instead of Dock
    await expect(widget.locator('button[title="Float"]')).toBeVisible();

    // Chat input should still be present
    await expect(page.locator('[data-testid="chat-input"]')).toBeVisible();
  });

  test('minimize shows bar, restore brings widget back', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open widget
    await page.locator('button:has-text("Chat with Architect")').click();
    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Minimize
    await widget.locator('button[title="Minimize"]').click();

    // Minimized bar should appear
    const bar = page.locator('[data-testid="chat-minimized-bar"]');
    await expect(bar).toBeVisible({ timeout: 3000 });

    // Click bar to restore
    await bar.click();

    // Full widget should be back
    await expect(page.locator('[data-testid="chat-title-bar"]')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('[data-testid="chat-input"]')).toBeVisible();
  });

  test('widget persists across page navigation', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open and minimize widget
    await page.locator('button:has-text("Chat with Architect")').click();
    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    await widget.locator('button[title="Minimize"]').click();
    const bar = page.locator('[data-testid="chat-minimized-bar"]');
    await expect(bar).toBeVisible({ timeout: 3000 });

    // Navigate to projects page
    await page.click('a[href="/projects"]');
    await page.waitForURL('**/projects');

    // Minimized bar should still be visible
    await expect(bar).toBeVisible();
  });

  test('close widget removes it', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    // Open widget
    await page.locator('button:has-text("Chat with Architect")').click();
    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Close
    await widget.locator('button[title="Close"]').click();

    // Widget should be gone
    await expect(widget).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Chat Widget — Lock & Messaging', () => {
  test('lock status dot is visible after opening', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    await page.locator('button:has-text("Chat with Architect")').click();
    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Lock status dot should be present
    const dot = page.locator('[data-testid="lock-status-dot"]');
    await expect(dot).toBeVisible({ timeout: 5000 });
  });

  test('can type in chat input', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    await page.locator('button:has-text("Chat with Architect")').click();
    await expect(page.locator('[data-testid="chat-widget"]')).toBeVisible({ timeout: 5000 });

    // Wait for connection (input should be enabled)
    const input = page.locator('[data-testid="chat-input"]');
    await expect(input).toBeVisible();

    // Type a message
    await input.fill('Hello architect');
    await expect(input).toHaveValue('Hello architect');
  });
});
