import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { checkLock, acquireLock, releaseLock, streamPrompt, BridgeApiError } from './bridge';

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(String(body)),
    body: null,
  } as unknown as Response;
}

describe('Bridge API client', () => {
  const mockFetch = vi.fn<typeof fetch>();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
    localStorage.clear();
    localStorage.setItem('vtf_token', 'test-token-123');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('checkLock', () => {
    it('sends GET to /v1/locks with project and role query params', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, []));

      await checkLock('my-project', 'architect');

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain('/v1/locks');
      expect(url).toContain('project=my-project');
      expect(url).toContain('role=architect');
      expect(options?.method).toBe('GET');
    });

    it('sends Authorization header from localStorage', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, []));

      await checkLock('proj', 'architect');

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Token test-token-123');
    });

    it('returns parsed lock array', async () => {
      const locks = [{ session_id: 'sess-1', role: 'architect', project: 'proj', user: 'admin' }];
      mockFetch.mockResolvedValueOnce(mockResponse(200, locks));

      const result = await checkLock('proj', 'architect');
      expect(result).toEqual(locks);
    });

    it('throws BridgeApiError on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(500, { detail: 'Server error' }));

      await expect(checkLock('proj', 'architect')).rejects.toThrow(BridgeApiError);
    });
  });

  describe('acquireLock', () => {
    it('sends POST to /v1/lock with JSON body', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(201, { session_id: 'sess-new' }));

      await acquireLock('my-project', 'architect');

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain('/v1/lock');
      expect(options?.method).toBe('POST');
      expect(JSON.parse(options?.body as string)).toEqual({
        project: 'my-project',
        role: 'architect',
      });
    });

    it('sends Authorization header', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(201, { session_id: 'sess-new' }));

      await acquireLock('proj', 'architect');

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Token test-token-123');
    });

    it('returns session_id from response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(201, { session_id: 'sess-abc' }));

      const result = await acquireLock('proj', 'architect');
      expect(result).toEqual({ session_id: 'sess-abc' });
    });

    it('throws BridgeApiError on conflict (409)', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(409, { detail: 'Lock held by another user' }));

      try {
        await acquireLock('proj', 'architect');
        expect.fail('Should have thrown');
      } catch (err) {
        expect(err).toBeInstanceOf(BridgeApiError);
        expect((err as BridgeApiError).status).toBe(409);
      }
    });
  });

  describe('releaseLock', () => {
    it('sends DELETE to /v1/lock with JSON body', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(204, null));

      await releaseLock('my-project', 'architect');

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain('/v1/lock');
      expect(options?.method).toBe('DELETE');
      expect(JSON.parse(options?.body as string)).toEqual({
        project: 'my-project',
        role: 'architect',
      });
    });

    it('resolves on 204 response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(204, null));

      await expect(releaseLock('proj', 'architect')).resolves.toBeUndefined();
    });

    it('throws BridgeApiError on error', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(404, { detail: 'No lock found' }));

      await expect(releaseLock('proj', 'architect')).rejects.toThrow(BridgeApiError);
    });
  });

  describe('streamPrompt', () => {
    it('sends POST to /v1/prompt/stream with correct body', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, null));

      await streamPrompt('hello', 'my-project', 'architect');

      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain('/v1/prompt/stream');
      expect(options?.method).toBe('POST');
      expect(JSON.parse(options?.body as string)).toEqual({
        message: 'hello',
        project: 'my-project',
        role: 'architect',
      });
    });

    it('sends Accept: application/x-ndjson header', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, null));

      await streamPrompt('hello', 'proj', 'architect');

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['Accept']).toBe('application/x-ndjson');
    });

    it('passes AbortSignal to fetch', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, null));
      const controller = new AbortController();

      await streamPrompt('hello', 'proj', 'architect', controller.signal);

      const [, options] = mockFetch.mock.calls[0];
      expect(options?.signal).toBe(controller.signal);
    });

    it('returns raw Response object', async () => {
      const rawResponse = mockResponse(200, null);
      mockFetch.mockResolvedValueOnce(rawResponse);

      const result = await streamPrompt('hello', 'proj', 'architect');
      expect(result).toBe(rawResponse);
    });

    it('throws BridgeApiError on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(401, { detail: 'Unauthorized' }));

      await expect(streamPrompt('hello', 'proj', 'architect')).rejects.toThrow(BridgeApiError);
    });
  });

  describe('auth edge cases', () => {
    it('throws when no vtf_token in localStorage', async () => {
      localStorage.removeItem('vtf_token');

      await expect(checkLock('proj', 'architect')).rejects.toThrow('No auth token');
    });
  });
});
