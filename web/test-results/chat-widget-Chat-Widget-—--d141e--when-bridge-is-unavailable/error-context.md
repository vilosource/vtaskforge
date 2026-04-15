# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: chat-widget.spec.ts >> Chat Widget — Lock & Messaging >> chat input is disabled when bridge is unavailable
- Location: e2e/chat-widget.spec.ts:193:3

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: page.goto: Test timeout of 60000ms exceeded.
Call log:
  - navigating to "https://vtf.dev.viloforge.com/", waiting until "load"

```

# Test source

```ts
  95  |   test('minimize shows bar, restore brings widget back', async ({ page }) => {
  96  |     await login(page);
  97  |     await page.goto(VTF_URL);
  98  | 
  99  |     // Open widget
  100 |     await page.locator('button:has-text("Chat with Architect")').click();
  101 |     const widget = page.locator('[data-testid="chat-widget"]');
  102 |     await expect(widget).toBeVisible({ timeout: 5000 });
  103 | 
  104 |     // Minimize
  105 |     await widget.locator('button[title="Minimize"]').click();
  106 | 
  107 |     // Minimized bar should appear
  108 |     const bar = page.locator('[data-testid="chat-minimized-bar"]');
  109 |     await expect(bar).toBeVisible({ timeout: 3000 });
  110 | 
  111 |     // Click bar to restore
  112 |     await bar.click();
  113 | 
  114 |     // Full widget should be back
  115 |     await expect(page.locator('[data-testid="chat-title-bar"]')).toBeVisible({ timeout: 3000 });
  116 |     await expect(page.locator('[data-testid="chat-input"]')).toBeVisible();
  117 |   });
  118 | 
  119 |   test('widget persists across page navigation', async ({ page }) => {
  120 |     await login(page);
  121 |     await page.goto(VTF_URL);
  122 | 
  123 |     // Open and minimize widget
  124 |     await page.locator('button:has-text("Chat with Architect")').click();
  125 |     const widget = page.locator('[data-testid="chat-widget"]');
  126 |     await expect(widget).toBeVisible({ timeout: 5000 });
  127 | 
  128 |     await widget.locator('button[title="Minimize"]').click();
  129 |     const bar = page.locator('[data-testid="chat-minimized-bar"]');
  130 |     await expect(bar).toBeVisible({ timeout: 3000 });
  131 | 
  132 |     // Navigate to projects page
  133 |     await page.click('a[href="/projects"]');
  134 |     await page.waitForURL('**/projects');
  135 | 
  136 |     // Minimized bar should still be visible
  137 |     await expect(bar).toBeVisible();
  138 |   });
  139 | 
  140 |   test('close widget removes it', async ({ page }) => {
  141 |     await login(page);
  142 |     await page.goto(VTF_URL);
  143 | 
  144 |     // Open widget
  145 |     await page.locator('button:has-text("Chat with Architect")').click();
  146 |     const widget = page.locator('[data-testid="chat-widget"]');
  147 |     await expect(widget).toBeVisible({ timeout: 5000 });
  148 | 
  149 |     // Close
  150 |     await widget.locator('button[title="Close"]').click();
  151 | 
  152 |     // Widget should be gone
  153 |     await expect(widget).not.toBeVisible({ timeout: 3000 });
  154 |   });
  155 | });
  156 | 
  157 | test.describe('Chat Widget — Session Auth', () => {
  158 |   test('chat widget does not show "No auth token" after session login', async ({ page }) => {
  159 |     await login(page);
  160 |     await page.goto(VTF_URL);
  161 | 
  162 |     await page.locator('button:has-text("Chat with Architect")').click();
  163 |     const widget = page.locator('[data-testid="chat-widget"]');
  164 |     await expect(widget).toBeVisible({ timeout: 5000 });
  165 | 
  166 |     // Wait for connection attempt to complete
  167 |     await page.waitForTimeout(3000);
  168 | 
  169 |     // Should NOT show "No auth token" — session login should provide a token
  170 |     const errorEl = page.locator('[data-testid="chat-error"]');
  171 |     const hasError = await errorEl.isVisible();
  172 |     if (hasError) {
  173 |       const errorText = await errorEl.textContent();
  174 |       expect(errorText).not.toContain('No auth token');
  175 |     }
  176 |   });
  177 | });
  178 | 
  179 | test.describe('Chat Widget — Lock & Messaging', () => {
  180 |   test('lock status dot is visible after opening', async ({ page }) => {
  181 |     await login(page);
  182 |     await page.goto(VTF_URL);
  183 | 
  184 |     await page.locator('button:has-text("Chat with Architect")').click();
  185 |     const widget = page.locator('[data-testid="chat-widget"]');
  186 |     await expect(widget).toBeVisible({ timeout: 5000 });
  187 | 
  188 |     // Lock status dot should be present
  189 |     const dot = page.locator('[data-testid="lock-status-dot"]');
  190 |     await expect(dot).toBeVisible({ timeout: 5000 });
  191 |   });
  192 | 
  193 |   test('chat input is disabled when bridge is unavailable', async ({ page }) => {
  194 |     await login(page);
> 195 |     await page.goto(VTF_URL);
      |                ^ Error: page.goto: Test timeout of 60000ms exceeded.
  196 | 
  197 |     await page.locator('button:has-text("Chat with Architect")').click();
  198 |     await expect(page.locator('[data-testid="chat-widget"]')).toBeVisible({ timeout: 5000 });
  199 | 
  200 |     const input = page.locator('[data-testid="chat-input"]');
  201 |     await expect(input).toBeVisible();
  202 | 
  203 |     // Without bridge API, input should be disabled (connection fails)
  204 |     await expect(input).toBeDisabled({ timeout: 10000 });
  205 | 
  206 |     // Connection error message should be shown
  207 |     await expect(page.locator('[data-testid="chat-error"]')).toBeVisible({ timeout: 5000 });
  208 |   });
  209 | });
  210 | 
  211 | test.describe('Chat Widget — Error States (mocked bridge)', () => {
  212 |   // Helper to mock bridge lock endpoints
  213 |   async function mockBridgeLock(
  214 |     page: Page,
  215 |     locksResponse: { status: number; body: unknown },
  216 |     lockPostResponse: { status: number; body: unknown },
  217 |   ) {
  218 |     // Mock GET /v1/locks (checkLock) — match bridge URL, not VTF API
  219 |     await page.route('**/bridge.dev.viloforge.com/v1/locks**', (route) => {
  220 |       route.fulfill({
  221 |         status: locksResponse.status,
  222 |         contentType: 'application/json',
  223 |         body: JSON.stringify(locksResponse.body),
  224 |       });
  225 |     });
  226 |     // Mock POST /v1/lock (acquireLock) — match bridge URL
  227 |     await page.route('**/bridge.dev.viloforge.com/v1/lock', (route) => {
  228 |       if (route.request().method() === 'POST') {
  229 |         route.fulfill({
  230 |           status: lockPostResponse.status,
  231 |           contentType: 'application/json',
  232 |           body: JSON.stringify(lockPostResponse.body),
  233 |         });
  234 |       } else {
  235 |         route.continue();
  236 |       }
  237 |     });
  238 |   }
  239 | 
  240 |   test('shows conflict message when lock is held by another user', async ({ page }) => {
  241 |     await login(page);
  242 |     // Ensure a token exists for bridge API client (session login doesn't set one)
  243 |     await page.evaluate(() => {
  244 |       if (!localStorage.getItem('vtf_token')) {
  245 |         localStorage.setItem('vtf_token', 'e2e-mock-token');
  246 |       }
  247 |     });
  248 |     await mockBridgeLock(
  249 |       page,
  250 |       { status: 200, body: [] },
  251 |       { status: 409, body: { detail: 'Lock held by alice' } },
  252 |     );
  253 | 
  254 |     await page.goto(VTF_URL);
  255 |     await page.locator('button:has-text("Chat with Architect")').click();
  256 | 
  257 |     const widget = page.locator('[data-testid="chat-widget"]');
  258 |     await expect(widget).toBeVisible({ timeout: 5000 });
  259 | 
  260 |     // Should show conflict error with username
  261 |     const error = page.locator('[data-testid="chat-error"]');
  262 |     await expect(error).toBeVisible({ timeout: 10000 });
  263 |     await expect(error).toContainText('alice');
  264 |   });
  265 | 
  266 |   test('shows unavailable message on 503', async ({ page }) => {
  267 |     await login(page);
  268 |     await page.evaluate(() => {
  269 |       if (!localStorage.getItem('vtf_token')) {
  270 |         localStorage.setItem('vtf_token', 'e2e-mock-token');
  271 |       }
  272 |     });
  273 |     await mockBridgeLock(
  274 |       page,
  275 |       { status: 200, body: [] },
  276 |       { status: 503, body: { detail: 'Failed to start agent session' } },
  277 |     );
  278 | 
  279 |     await page.goto(VTF_URL);
  280 |     await page.locator('button:has-text("Chat with Architect")').click();
  281 | 
  282 |     const widget = page.locator('[data-testid="chat-widget"]');
  283 |     await expect(widget).toBeVisible({ timeout: 5000 });
  284 | 
  285 |     const error = page.locator('[data-testid="chat-error"]');
  286 |     await expect(error).toBeVisible({ timeout: 10000 });
  287 |     await expect(error).toContainText('unavailable');
  288 |   });
  289 | });
  290 | 
```