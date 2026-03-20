import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiGet, apiPost, apiPatch, apiDelete, ApiError, apiGetPaginated } from './client';

// Helper to create a mock Response
function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(String(body)),
  } as unknown as Response;
}

describe('API client', () => {
  const mockFetch = vi.fn<typeof fetch>();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
    localStorage.clear();
    // Reset document.cookie
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: '',
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('apiGet', () => {
    it('sends credentials: include for session auth', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, { id: 1 }));

      await apiGet('/v1/workplans/');

      expect(mockFetch).toHaveBeenCalledWith(
        '/v1/workplans/',
        expect.objectContaining({ credentials: 'include' }),
      );
    });

    it('does NOT send Authorization header when no token in localStorage', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, {}));

      await apiGet('/v1/workplans/');

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['Authorization']).toBeUndefined();
    });

    it('sends Token header when token is in localStorage', async () => {
      localStorage.setItem('vtf_token', 'abc123');
      mockFetch.mockResolvedValueOnce(mockResponse(200, {}));

      await apiGet('/v1/workplans/');

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Token abc123');
    });

    it('throws ApiError on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(404, { detail: 'Not found' }));

      await expect(apiGet('/v1/workplans/999/')).rejects.toThrow(ApiError);
    });

    it('throws ApiError with correct status', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(403, { detail: 'Forbidden' }));

      try {
        await apiGet('/v1/workplans/');
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError);
        expect((err as ApiError).status).toBe(403);
      }
    });
  });

  describe('apiPost', () => {
    it('sends credentials: include', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(201, { id: 2 }));

      await apiPost('/v1/workplans/', { title: 'New' });

      expect(mockFetch).toHaveBeenCalledWith(
        '/v1/workplans/',
        expect.objectContaining({ credentials: 'include' }),
      );
    });

    it('sends X-CSRFToken header from cookie', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrftoken=mytoken123',
      });
      mockFetch.mockResolvedValueOnce(mockResponse(201, { id: 2 }));

      await apiPost('/v1/workplans/', { title: 'New' });

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['X-CSRFToken']).toBe('mytoken123');
    });

    it('sends JSON body', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(201, { id: 2 }));
      const body = { title: 'Test workplan' };

      await apiPost('/v1/workplans/', body);

      const [, options] = mockFetch.mock.calls[0];
      expect(options?.body).toBe(JSON.stringify(body));
    });

    it('sends Token header when token is in localStorage', async () => {
      localStorage.setItem('vtf_token', 'mytoken');
      mockFetch.mockResolvedValueOnce(mockResponse(201, {}));

      await apiPost('/v1/workplans/', {});

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['Authorization']).toBe('Token mytoken');
    });
  });

  describe('apiPatch', () => {
    it('sends PATCH method', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(200, { id: 1 }));

      await apiPatch('/v1/workplans/1/', { title: 'Updated' });

      const [, options] = mockFetch.mock.calls[0];
      expect(options?.method).toBe('PATCH');
    });

    it('sends X-CSRFToken header', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrftoken=patchtoken',
      });
      mockFetch.mockResolvedValueOnce(mockResponse(200, {}));

      await apiPatch('/v1/workplans/1/', {});

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['X-CSRFToken']).toBe('patchtoken');
    });
  });

  describe('apiDelete', () => {
    it('sends DELETE method', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse(204, null));

      await apiDelete('/v1/workplans/1/');

      const [, options] = mockFetch.mock.calls[0];
      expect(options?.method).toBe('DELETE');
    });

    it('sends X-CSRFToken header', async () => {
      Object.defineProperty(document, 'cookie', {
        writable: true,
        value: 'csrftoken=deletetoken',
      });
      mockFetch.mockResolvedValueOnce(mockResponse(204, null));

      await apiDelete('/v1/workplans/1/');

      const [, options] = mockFetch.mock.calls[0];
      const headers = options?.headers as Record<string, string>;
      expect(headers['X-CSRFToken']).toBe('deletetoken');
    });
  });

  describe('apiGetPaginated', () => {
    it('unwraps results from paginated response', async () => {
      const items = [{ id: 1 }, { id: 2 }];
      mockFetch.mockResolvedValueOnce(
        mockResponse(200, { count: 2, next: null, previous: null, results: items }),
      );

      const result = await apiGetPaginated('/v1/workplans/');

      expect(result).toEqual(items);
    });
  });

  describe('ApiError', () => {
    it('has correct name, status and data properties', () => {
      const err = new ApiError(422, { detail: 'Invalid' });
      expect(err.name).toBe('ApiError');
      expect(err.status).toBe(422);
      expect(err.data).toEqual({ detail: 'Invalid' });
      expect(err.message).toBe('API error 422');
    });

    it('is an instance of Error', () => {
      const err = new ApiError(500, 'Server error');
      expect(err).toBeInstanceOf(Error);
    });
  });
});
