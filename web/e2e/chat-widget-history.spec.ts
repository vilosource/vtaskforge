/**
 * Phase 9 E2E test for prior conversation history rendering in the chat widget.
 *
 * Verifies that when a user opens the chat widget on a project that has prior
 * architect sessions, the project-scoped history is fetched and rendered as a
 * collapsed expander with user attribution.
 *
 * Requires: vtf + bridge live at VTF_BASE_URL / BRIDGE_BASE_URL.
 *           Test uses a fresh UUID-suffixed project so it doesn't depend on
 *           any pre-seeded history.
 */

import { test, expect, Page, request } from '@playwright/test';

const VTF_URL = process.env.VTF_BASE_URL || 'http://localhost:9999';
const BRIDGE_URL = process.env.BRIDGE_BASE_URL || 'http://localhost:8081';
const ADMIN_USER = process.env.VTF_USERNAME || 'admin';
const ADMIN_PASS = process.env.VTF_PASSWORD || 'admin';

interface FixtureState {
  projectId: string;
  token: string;
  nonce: string;
}

async function loginUI(page: Page) {
  await page.goto(`${VTF_URL}/login`);
  await page.fill('input[name="username"], input[type="text"]', ADMIN_USER);
  await page.fill('input[name="password"], input[type="password"]', ADMIN_PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL('**/');
}

async function setup(): Promise<FixtureState> {
  // Use the request fixture's API client for setup so we don't depend on UI.
  const ctx = await request.newContext({ ignoreHTTPSErrors: true });
  // Login to get CSRF + token
  await ctx.get(`${VTF_URL}/v1/auth/login`);
  const cookies = (await ctx.storageState()).cookies;
  const csrf = cookies.find((c) => c.name === 'csrftoken')?.value || '';
  await ctx.post(`${VTF_URL}/v1/auth/login`, {
    headers: { 'X-CSRFToken': csrf, 'Referer': VTF_URL + '/' },
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  const cookies2 = (await ctx.storageState()).cookies;
  const csrf2 = cookies2.find((c) => c.name === 'csrftoken')?.value || csrf;
  const tokResp = await ctx.post(`${VTF_URL}/v1/auth/token/`, {
    headers: { 'X-CSRFToken': csrf2, 'Referer': VTF_URL + '/' },
  });
  const token = (await tokResp.json()).token;

  const nonce = Math.random().toString(36).slice(2, 10);
  // Create project
  const projResp = await ctx.post(`${VTF_URL}/v1/projects/`, {
    headers: { 'Authorization': `Token ${token}` },
    data: {
      name: `phase9-e2e-${nonce}`,
      description: 'Phase 9 widget e2e — auto-created, safe to delete',
      repo_url: 'git@github.com:vilosource/vafi-smoke-test.git',
      default_branch: 'main',
    },
  });
  const projectId = (await projResp.json()).id;

  // Acquire architect lock and send a single attributed prompt so the history
  // endpoint will return a known turn.
  await ctx.post(`${BRIDGE_URL}/v1/lock`, {
    headers: { 'Authorization': `Token ${token}` },
    data: { project: projectId, role: 'architect' },
  });
  await ctx.post(`${BRIDGE_URL}/v1/prompt/stream`, {
    headers: { 'Authorization': `Token ${token}`, 'Accept': 'application/x-ndjson' },
    data: {
      message: `Phase9 e2e marker ${nonce}: please acknowledge.`,
      project: projectId, role: 'architect',
    },
  });
  await ctx.delete(`${BRIDGE_URL}/v1/lock`, {
    headers: { 'Authorization': `Token ${token}` },
    data: { project: projectId, role: 'architect' },
  });

  await ctx.dispose();
  return { projectId, token, nonce };
}

async function teardown(state: FixtureState) {
  const ctx = await request.newContext({ ignoreHTTPSErrors: true });
  await ctx.delete(`${VTF_URL}/v1/projects/${state.projectId}/`, {
    headers: { 'Authorization': `Token ${state.token}` },
  });
  await ctx.dispose();
}

test.describe('Chat Widget — Phase 9 prior history', () => {
  test('shows collapsed expander with attributed user message after prior session', async ({ page }) => {
    const fixture = await setup();
    try {
      await loginUI(page);
      await page.goto(`${VTF_URL}/projects/${fixture.projectId}`);

      // Open the chat widget
      const chatBtn = page.locator('button:has-text("Chat with Architect")');
      await expect(chatBtn).toBeVisible({ timeout: 10000 });
      await chatBtn.click();

      // Prior history panel should appear collapsed by default
      const toggle = page.locator('[data-testid="prior-history-toggle"]');
      await expect(toggle).toBeVisible({ timeout: 10000 });
      await expect(toggle).toContainText('View prior conversation');
      await expect(toggle).toContainText('1 message');

      // Content hidden until click
      await expect(page.locator('[data-testid="prior-history-content"]')).toHaveCount(0);

      // Expand
      await toggle.click();
      await expect(page.locator('[data-testid="prior-history-content"]')).toBeVisible();

      // The user-attributed turn should show: label "admin" + the planted text
      const userTurn = page.locator('[data-testid="prior-history-turn-0"]');
      await expect(userTurn).toContainText('admin');
      await expect(userTurn).toContainText(`Phase9 e2e marker ${fixture.nonce}`);

      // The assistant turn should be labeled "Architect"
      const archTurn = page.locator('[data-testid="prior-history-turn-1"]');
      await expect(archTurn).toContainText('Architect');
    } finally {
      await teardown(fixture);
    }
  });
});
