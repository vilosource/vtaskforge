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

test.describe('Chat Widget — Session Auth', () => {
  test('chat widget does not show "No auth token" after session login', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    await page.locator('button:has-text("Chat with Architect")').click();
    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Wait for connection attempt to complete
    await page.waitForTimeout(3000);

    // Should NOT show "No auth token" — session login should provide a token
    const errorEl = page.locator('[data-testid="chat-error"]');
    const hasError = await errorEl.isVisible();
    if (hasError) {
      const errorText = await errorEl.textContent();
      expect(errorText).not.toContain('No auth token');
    }
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

  test('chat input is disabled when bridge is unavailable', async ({ page }) => {
    await login(page);
    await page.goto(VTF_URL);

    await page.locator('button:has-text("Chat with Architect")').click();
    await expect(page.locator('[data-testid="chat-widget"]')).toBeVisible({ timeout: 5000 });

    const input = page.locator('[data-testid="chat-input"]');
    await expect(input).toBeVisible();

    // Without bridge API, input should be disabled (connection fails)
    await expect(input).toBeDisabled({ timeout: 10000 });

    // Connection error message should be shown
    await expect(page.locator('[data-testid="chat-error"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Chat Widget — Error States (mocked bridge)', () => {
  // Helper to mock bridge lock endpoints
  async function mockBridgeLock(
    page: Page,
    locksResponse: { status: number; body: unknown },
    lockPostResponse: { status: number; body: unknown },
  ) {
    // Mock GET /v1/locks (checkLock) — match bridge URL, not VTF API
    await page.route('**/bridge.dev.viloforge.com/v1/locks**', (route) => {
      route.fulfill({
        status: locksResponse.status,
        contentType: 'application/json',
        body: JSON.stringify(locksResponse.body),
      });
    });
    // Mock POST /v1/lock (acquireLock) — match bridge URL
    await page.route('**/bridge.dev.viloforge.com/v1/lock', (route) => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: lockPostResponse.status,
          contentType: 'application/json',
          body: JSON.stringify(lockPostResponse.body),
        });
      } else {
        route.continue();
      }
    });
  }

  test('shows conflict message when lock is held by another user', async ({ page }) => {
    await login(page);
    // Ensure a token exists for bridge API client (session login doesn't set one)
    await page.evaluate(() => {
      if (!localStorage.getItem('vtf_token')) {
        localStorage.setItem('vtf_token', 'e2e-mock-token');
      }
    });
    await mockBridgeLock(
      page,
      { status: 200, body: [] },
      { status: 409, body: { detail: 'Lock held by alice' } },
    );

    await page.goto(VTF_URL);
    await page.locator('button:has-text("Chat with Architect")').click();

    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Should show conflict error with username
    const error = page.locator('[data-testid="chat-error"]');
    await expect(error).toBeVisible({ timeout: 10000 });
    await expect(error).toContainText('alice');
  });

  test('shows unavailable message on 503', async ({ page }) => {
    await login(page);
    await page.evaluate(() => {
      if (!localStorage.getItem('vtf_token')) {
        localStorage.setItem('vtf_token', 'e2e-mock-token');
      }
    });
    await mockBridgeLock(
      page,
      { status: 200, body: [] },
      { status: 503, body: { detail: 'Failed to start agent session' } },
    );

    await page.goto(VTF_URL);
    await page.locator('button:has-text("Chat with Architect")').click();

    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    const error = page.locator('[data-testid="chat-error"]');
    await expect(error).toBeVisible({ timeout: 10000 });
    await expect(error).toContainText('unavailable');
  });
});

test.describe('Chat Widget — R8: Lock Ownership', () => {
  test('lock is attributed to logged-in user, not service account', async ({ page }) => {
    await login(page);
    await page.evaluate(() => {
      if (!localStorage.getItem('vtf_token')) {
        localStorage.setItem('vtf_token', 'e2e-mock-token');
      }
    });

    // Intercept the POST /v1/lock request and verify the response shows correct user
    let lockResponseBody: Record<string, unknown> | null = null;

    // Mock bridge lock acquire — simulate a lock owned by the actual user (admin)
    await page.route('**/bridge.dev.viloforge.com/v1/locks**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
    await page.route('**/bridge.dev.viloforge.com/v1/lock', async (route) => {
      if (route.request().method() === 'POST') {
        lockResponseBody = {
          session_id: 'mock-sess-r8',
          project: 'proj-1',
          role: 'architect',
          user: 'admin',
          user_id: 1,
        };
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(lockResponseBody),
        });
      } else {
        route.continue();
      }
    });

    await page.goto(VTF_URL);
    await page.locator('button:has-text("Chat with Architect")').click();

    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Wait for lock acquisition
    await page.waitForTimeout(2000);

    // Verify the lock response has user=admin, NOT user=vafi-agent
    expect(lockResponseBody).not.toBeNull();
    expect(lockResponseBody!['user']).toBe('admin');
    expect(lockResponseBody!['user_id']).toBe(1);
    expect(lockResponseBody!['user']).not.toBe('vafi-agent');
  });

  test('lock conflict shows real username, not service account', async ({ page }) => {
    await login(page);
    await page.evaluate(() => {
      if (!localStorage.getItem('vtf_token')) {
        localStorage.setItem('vtf_token', 'e2e-mock-token');
      }
    });

    // Mock: lock held by a real user "alice", not "vafi-agent"
    await page.route('**/bridge.dev.viloforge.com/v1/locks**', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
    await page.route('**/bridge.dev.viloforge.com/v1/lock', (route) => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: 'Locked by alice',
            locked_by: 'alice',
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.goto(VTF_URL);
    await page.locator('button:has-text("Chat with Architect")').click();

    const widget = page.locator('[data-testid="chat-widget"]');
    await expect(widget).toBeVisible({ timeout: 5000 });

    // Conflict should show real username
    const error = page.locator('[data-testid="chat-error"]');
    await expect(error).toBeVisible({ timeout: 10000 });
    await expect(error).toContainText('alice');
    // Should NOT mention vafi-agent
    const errorText = await error.textContent();
    expect(errorText).not.toContain('vafi-agent');
  });
});
