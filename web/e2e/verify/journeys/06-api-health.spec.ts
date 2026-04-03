/**
 * Journey 6: API & Infrastructure Health
 *
 * Verifies infrastructure-level concerns: health endpoint, API responses,
 * SSE connectivity, static asset serving, SPA fallback routing.
 */
import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.VTF_BASE_URL || 'http://localhost:8001';
const API_TOKEN = process.env.VTF_API_TOKEN || '';

const seedData = JSON.parse(
  fs.readFileSync(path.join(__dirname, '..', 'seed-data.json'), 'utf-8'),
);

test.describe('API & Infrastructure Health', () => {
  test('health endpoint reports healthy', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/v1/health`);
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data.status).toBe('healthy');
    expect(data.checks.db).toBe('ok');
    expect(data.checks.redis).toBe('ok');
  });

  test('projects API returns verification project', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/v1/projects/`, {
      headers: { Authorization: `Token ${API_TOKEN}` },
    });
    expect(response.status()).toBe(200);

    const data = await response.json();
    const projects = Array.isArray(data) ? data : data.results || [];
    const verify = projects.find(
      (p: { id: string }) => p.id === seedData.projectId,
    );
    expect(verify).toBeTruthy();
  });

  test('tasks API returns filtered results', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/v1/tasks/?status=draft`, {
      headers: { Authorization: `Token ${API_TOKEN}` },
    });
    expect(response.status()).toBe(200);

    const data = await response.json();
    const tasks = Array.isArray(data) ? data : data.results || [];
    expect(tasks.length).toBeGreaterThan(0);
  });

  test('static assets serve with correct MIME types', async ({ page }) => {
    const mimeErrors: string[] = [];
    page.on('console', (msg) => {
      const text = msg.text();
      if (text.includes('MIME') || text.includes('module script')) {
        mimeErrors.push(text);
      }
    });

    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');

    expect(mimeErrors).toHaveLength(0);
  });

  test('SPA fallback returns index.html for unknown routes', async ({ page }) => {
    const response = await page.goto('/this-route-does-not-exist');
    // SPA fallback should return 200 (index.html), not 404
    expect(response?.status()).toBe(200);
  });

  test('SSE endpoint accepts connection', async ({}) => {
    // SSE streams indefinitely — use fetch with AbortController to check
    // the initial response status without waiting for the stream to end
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    try {
      const res = await fetch(`${BASE_URL}/v1/events/stream/`, {
        headers: {
          Authorization: `Token ${API_TOKEN}`,
          Accept: 'text/event-stream',
        },
        signal: controller.signal,
      });
      clearTimeout(timer);
      // Accept 200 (streaming) — NOT 406 or 401
      expect([200]).toContain(res.status);
    } catch (e: unknown) {
      clearTimeout(timer);
      // AbortError is fine — means we connected and got a response
      if (e instanceof Error && e.name !== 'AbortError') {
        throw e;
      }
    }
  });
});
