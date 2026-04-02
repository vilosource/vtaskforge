/**
 * Playwright E2E tests for User Management UI.
 *
 * Runs against the dogfood instance (port 8001) with real auth and API.
 *
 * Prerequisites:
 *   - docker compose -f docker-compose.dogfood.yml up -d
 *   - Admin user exists (admin/admin)
 *   - Seed data applied (testuser, channel mapping, agent lock)
 *
 * Run:
 *   cd web && npx playwright test tests/user-management.spec.ts
 */
import { test, expect, type Page, type BrowserContext } from '@playwright/test';

const DOGFOOD_URL = process.env.DOGFOOD_URL || 'http://localhost:8001';
const TIMEOUT = 10000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function loginAs(
  browser: { newContext: () => Promise<BrowserContext> },
  username: string,
  password: string,
): Promise<{ context: BrowserContext; page: Page }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(`${DOGFOOD_URL}/login`);
  await page.getByRole('textbox', { name: 'Username' }).fill(username);
  await page.getByRole('textbox', { name: 'Password' }).fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  // Wait for redirect away from login
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: TIMEOUT });
  // Wait for auth to settle (validate endpoint runs after login redirect)
  await page.waitForTimeout(2000);
  return { context, page };
}

// ---------------------------------------------------------------------------
// Profile page
// ---------------------------------------------------------------------------

test.describe('Profile page', () => {
  test('renders profile sections', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/settings`);
    await expect(page.getByRole('heading', { name: 'Profile' })).toBeVisible({ timeout: TIMEOUT });
    await expect(page.getByText('Project Memberships')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Linked Accounts' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Session History' })).toBeVisible();

    await context.close();
  });

  test('shows project memberships for admin', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/settings`);
    await expect(page.getByRole('heading', { name: 'Profile' })).toBeVisible({ timeout: TIMEOUT });

    // Admin should have e2e-project membership (from seed)
    await expect(page.getByText('e2e-project')).toBeVisible({ timeout: TIMEOUT });

    await context.close();
  });

  test('link account form toggles', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/settings`);
    await expect(page.getByRole('heading', { name: 'Profile' })).toBeVisible({ timeout: TIMEOUT });

    // Open form
    await page.getByText('Link Account').click();
    await expect(page.getByPlaceholder('Provider')).toBeVisible();
    await expect(page.getByPlaceholder('External ID')).toBeVisible();

    // Cancel closes form
    await page.getByRole('button', { name: 'Cancel' }).first().click();
    await expect(page.getByPlaceholder('Provider')).not.toBeVisible();

    await context.close();
  });
});

// ---------------------------------------------------------------------------
// Sidebar admin section
// ---------------------------------------------------------------------------

test.describe('Sidebar admin section', () => {
  test('staff user sees admin links in sidebar', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    // The sidebar should have the Admin section header and links
    const sidebar = page.locator('aside');
    await expect(sidebar.getByText('Admin', { exact: true })).toBeVisible({ timeout: TIMEOUT });
    await expect(sidebar.getByRole('link', { name: 'Users' })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Locks' })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: 'Channels' })).toBeVisible();

    await context.close();
  });

  test('admin links navigate to correct routes', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    const sidebar = page.locator('aside');

    await sidebar.getByRole('link', { name: 'Users' }).click();
    await page.waitForURL('**/manage/users', { timeout: TIMEOUT });

    await sidebar.getByRole('link', { name: 'Locks' }).click();
    await page.waitForURL('**/manage/locks', { timeout: TIMEOUT });

    await sidebar.getByRole('link', { name: 'Channels' }).click();
    await page.waitForURL('**/manage/channel-mappings', { timeout: TIMEOUT });

    await context.close();
  });

  test('non-staff user does not see admin section', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'testuser', 'testpass');

    const sidebar = page.locator('aside');
    // Admin section header should not be visible
    await expect(sidebar.getByText('Admin', { exact: true })).not.toBeVisible();

    await context.close();
  });
});

// ---------------------------------------------------------------------------
// Staff-only guard
// ---------------------------------------------------------------------------

test.describe('Staff-only route guard', () => {
  test('non-staff redirected away from /manage/users', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'testuser', 'testpass');

    await page.goto(`${DOGFOOD_URL}/manage/users`);
    await page.waitForTimeout(2000);

    // Should not be on admin page — redirected to home
    expect(page.url()).not.toContain('/manage/users');

    await context.close();
  });
});

// ---------------------------------------------------------------------------
// Admin Users page
// ---------------------------------------------------------------------------

test.describe('Admin Users page', () => {
  test('renders user table with data', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/manage/users`);
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible({ timeout: TIMEOUT });

    // Table should render
    await expect(page.locator('table')).toBeVisible({ timeout: TIMEOUT });

    // Should have at least one row with a username
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: TIMEOUT });

    await context.close();
  });

  test('search input filters users', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/manage/users`);
    await expect(page.locator('table')).toBeVisible({ timeout: TIMEOUT });

    // Type in search
    await page.getByPlaceholder('Search users...').fill('testuser');
    await page.waitForTimeout(1500);

    // Should show testuser in results
    await expect(page.locator('table').getByText('testuser')).toBeVisible({ timeout: TIMEOUT });

    await context.close();
  });

  test('create service account flow', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/manage/users`);
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible({ timeout: TIMEOUT });

    // Open create form
    await page.getByText('Create Service Account').click();
    await expect(page.getByPlaceholder('Account name')).toBeVisible();

    // Create with unique name
    const name = `pw-sa-${Date.now()}`;
    await page.getByPlaceholder('Account name').fill(name);
    await page.getByRole('button', { name: 'Create' }).click();

    // Token should appear
    await expect(page.getByText('Service account created')).toBeVisible({ timeout: TIMEOUT });
    await expect(page.getByText('Save this token')).toBeVisible();

    await context.close();
  });
});

// ---------------------------------------------------------------------------
// Admin Locks page
// ---------------------------------------------------------------------------

test.describe('Admin Locks page', () => {
  test('renders page heading', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/manage/locks`);
    await expect(page.getByRole('heading', { name: 'Agent Locks' })).toBeVisible({ timeout: TIMEOUT });

    await context.close();
  });

  test('force release shows confirmation inline', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/manage/locks`);
    await page.waitForTimeout(2000);

    const releaseBtn = page.getByText('Force Release').first();
    if (await releaseBtn.isVisible()) {
      await releaseBtn.click();

      // Confirmation should appear
      await expect(page.getByText('Release?')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Yes' })).toBeVisible();

      // Cancel
      await page.getByRole('button', { name: 'No' }).first().click();
      await expect(page.getByText('Release?')).not.toBeVisible();
    }

    await context.close();
  });
});

// ---------------------------------------------------------------------------
// Admin Channel Mappings page
// ---------------------------------------------------------------------------

test.describe('Admin Channel Mappings page', () => {
  test('renders page with seeded mapping', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/manage/channel-mappings`);
    await expect(page.getByRole('heading', { name: 'Channel Mappings' })).toBeVisible({ timeout: TIMEOUT });

    // Seeded mapping should appear
    await expect(page.getByText('C-E2E-TEST')).toBeVisible({ timeout: TIMEOUT });

    await context.close();
  });

  test('add mapping form creates entry', async ({ browser }) => {
    const { context, page } = await loginAs(browser, 'admin', 'admin');

    await page.goto(`${DOGFOOD_URL}/manage/channel-mappings`);
    await expect(page.getByRole('heading', { name: 'Channel Mappings' })).toBeVisible({ timeout: TIMEOUT });

    // Open form
    await page.getByText('Add Mapping').click();
    await expect(page.getByPlaceholder('Provider')).toBeVisible();

    // Fill and submit
    const uniqueId = `C-PW-${Date.now()}`;
    await page.getByPlaceholder('Provider').fill('slack');
    await page.getByPlaceholder('Channel ID').fill(uniqueId);
    await page.getByPlaceholder('Display Name').fill('#pw-test');
    await page.getByPlaceholder('Project ID').fill('e2e-project');
    await page.getByRole('button', { name: 'Save' }).click();

    // New mapping should appear in table
    await expect(page.getByText(uniqueId)).toBeVisible({ timeout: TIMEOUT });

    await context.close();
  });
});
