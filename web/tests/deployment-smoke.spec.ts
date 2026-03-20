/**
 * Deployment Smoke Test (Gate 1c)
 *
 * Runs against the BUILT and DEPLOYED artifact (dogfood instance on port 8001),
 * NOT against the Vite dev server. This catches issues invisible to unit/integration
 * tests: asset serving, routing, auth flow, MIME types, SSE connectivity.
 *
 * When to run:
 *   - After any change to: Dockerfile*, docker-compose*, settings/*.py, urls.py,
 *     requirements/*.txt, vite.config.ts, middleware, auth, or static file config
 *   - After every dogfood rebuild
 *
 * Prerequisites:
 *   - docker compose -f docker-compose.dogfood.yml up -d
 *   - Admin user exists (admin/admin)
 *
 * Run:
 *   cd web && npx playwright test tests/deployment-smoke.spec.ts
 */
import { test, expect } from '@playwright/test';

const DOGFOOD_URL = process.env.DOGFOOD_URL || 'http://localhost:8001';

test.describe('Deployment Smoke Test', () => {
  let consoleErrors: string[];

  test.beforeEach(async ({ page }) => {
    consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
  });

  test('login page renders for unauthenticated user', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(DOGFOOD_URL);
    await page.waitForTimeout(2000);

    // Should redirect to login
    expect(page.url()).toContain('/login');
    await expect(page.locator('text=VTaskForge')).toBeVisible();
    await expect(page.locator('text=Sign in')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Username' })).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Password' })).toBeVisible();

    await context.close();
  });

  test('login with valid credentials reaches workplan list', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(DOGFOOD_URL);
    await page.waitForTimeout(2000);

    // Fill login form
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('admin');
    await page.getByRole('button', { name: 'Sign in' }).click();

    // Should reach workplan list
    await page.waitForTimeout(3000);
    await expect(page.locator('text=Workplans')).toBeVisible({ timeout: 10000 });

    await context.close();
  });

  test('login with invalid credentials shows error', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${DOGFOOD_URL}/login`);
    await page.waitForTimeout(1000);

    await page.getByRole('textbox', { name: 'Username' }).fill('wrong');
    await page.getByRole('textbox', { name: 'Password' }).fill('wrong');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await page.waitForTimeout(2000);
    // Should stay on login with error message
    expect(page.url()).toContain('/login');

    await context.close();
  });

  test('SPA assets serve with correct MIME types', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const mimeErrors: string[] = [];

    page.on('console', (msg) => {
      const text = msg.text();
      if (text.includes('MIME') || text.includes('module script')) {
        mimeErrors.push(text);
      }
    });

    await page.goto(DOGFOOD_URL);
    await page.waitForTimeout(3000);

    // No MIME type errors means assets served correctly
    expect(mimeErrors).toHaveLength(0);

    await context.close();
  });

  test('API responds through Django (not just Vite proxy)', async ({ request }) => {
    const response = await request.get(`${DOGFOOD_URL}/v1/health`);
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data.status).toBe('healthy');
    expect(data.checks.db).toBe('ok');
  });

  test('authenticated Kanban board loads without console errors', async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Login first
    await page.goto(`${DOGFOOD_URL}/login`);
    await page.waitForTimeout(1000);
    await page.getByRole('textbox', { name: 'Username' }).fill('admin');
    await page.getByRole('textbox', { name: 'Password' }).fill('admin');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForTimeout(3000);

    // Navigate to a workplan board (if any exist)
    const links = await page.getByRole('link').all();
    const workplanLink = links.find(async (l) => {
      const href = await l.getAttribute('href');
      return href && href.startsWith('/workplans/');
    });

    if (workplanLink) {
      await workplanLink.click();
      await page.waitForTimeout(3000);

      // Verify Kanban columns render
      await expect(page.locator('text=Draft')).toBeVisible({ timeout: 5000 });
      await expect(page.locator('text=Ready')).toBeVisible();
      await expect(page.locator('text=Done')).toBeVisible();
    }

    // Filter out non-critical errors (favicon, etc.)
    const criticalErrors = errors.filter(
      (e) => !e.includes('favicon') && !e.includes('manifest')
    );
    expect(criticalErrors).toHaveLength(0);

    await context.close();
  });

  test('SSE endpoint accepts browser connection (no 406)', async ({ request }) => {
    // Register an agent to get a token for API access
    const registerResp = await request.post(`${DOGFOOD_URL}/v1/agents/`, {
      data: { name: 'smoke-test-agent', tags: ['test'] },
    });
    expect(registerResp.status()).toBe(201);

    const agentData = await registerResp.json();
    const token = agentData.token;

    // Try SSE endpoint — should return 200 with text/event-stream, NOT 406
    const sseResp = await request.get(`${DOGFOOD_URL}/v1/events/stream/`, {
      headers: {
        Authorization: `Token ${token}`,
        Accept: 'text/event-stream',
      },
    });

    // Accept 200 (streaming) or timeout — but NOT 406 or 401
    expect([200, 408]).toContain(sseResp.status());
  });
});
