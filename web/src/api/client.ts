const BASE_URL = '';  // relative — Vite proxy handles /v1

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(`API error ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('vtf_token');
  if (token) {
    return { Authorization: `Token ${token}` };
  }
  return {};  // session auth via cookie — browser sends automatically
}

function getCsrfToken(): string {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

function getCsrfHeaders(method: string): Record<string, string> {
  const safeMethods = ['GET', 'HEAD', 'OPTIONS', 'TRACE'];
  if (safeMethods.includes(method.toUpperCase())) {
    return {};
  }
  const csrfToken = getCsrfToken();
  return csrfToken ? { 'X-CSRFToken': csrfToken } : {};
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let data: unknown;
    try {
      data = await res.json();
    } catch {
      data = await res.text();
    }
    throw new ApiError(res.status, data);
  }
  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'GET',
    credentials: 'include',  // send cookies for session auth
    headers: {
      ...getAuthHeaders(),
      ...getCsrfHeaders('GET'),
      Accept: 'application/json',
    },
  });
  return handleResponse<T>(res);
}

export async function apiGetPaginated<T>(path: string): Promise<T[]> {
  const data = await apiGet<PaginatedResponse<T>>(path);
  return data.results;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      ...getAuthHeaders(),
      ...getCsrfHeaders('POST'),
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      ...getAuthHeaders(),
      ...getCsrfHeaders('PATCH'),
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'DELETE',
    credentials: 'include',
    headers: {
      ...getAuthHeaders(),
      ...getCsrfHeaders('DELETE'),
      Accept: 'application/json',
    },
  });
  return handleResponse<T>(res);
}
