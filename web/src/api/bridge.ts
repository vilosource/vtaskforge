import type { BridgeLock, BridgeLockResponse } from '../types/chat';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const BRIDGE_URL = ((globalThis as any).__BRIDGE_URL as string) || 'https://bridge.dev.viloforge.com';

export class BridgeApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(`Bridge API error ${status}`);
    this.name = 'BridgeApiError';
    this.status = status;
    this.data = data;
  }
}

function getToken(): string {
  const token = localStorage.getItem('vtf_token');
  if (!token) {
    throw new Error('No auth token available');
  }
  return token;
}

function authHeaders(): Record<string, string> {
  return { Authorization: `Token ${getToken()}` };
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let data: unknown;
    try {
      data = await res.json();
    } catch {
      data = await res.text();
    }
    throw new BridgeApiError(res.status, data);
  }
  if (res.status === 204) {
    return undefined as unknown as T;
  }
  return res.json() as Promise<T>;
}

export async function checkLock(project: string, role: string): Promise<BridgeLock[]> {
  const params = new URLSearchParams({ project, role });
  const res = await fetch(`${BRIDGE_URL}/v1/locks?${params}`, {
    method: 'GET',
    headers: {
      ...authHeaders(),
      Accept: 'application/json',
    },
  });
  return handleResponse<BridgeLock[]>(res);
}

export async function acquireLock(project: string, role: string): Promise<BridgeLockResponse> {
  const res = await fetch(`${BRIDGE_URL}/v1/lock`, {
    method: 'POST',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ project, role }),
  });
  return handleResponse<BridgeLockResponse>(res);
}

export async function releaseLock(project: string, role: string): Promise<void> {
  const res = await fetch(`${BRIDGE_URL}/v1/lock`, {
    method: 'DELETE',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ project, role }),
  });
  return handleResponse<void>(res);
}

export async function streamPrompt(
  message: string,
  project: string,
  role: string,
  signal?: AbortSignal,
): Promise<Response> {
  const res = await fetch(`${BRIDGE_URL}/v1/prompt/stream`, {
    method: 'POST',
    headers: {
      ...authHeaders(),
      'Content-Type': 'application/json',
      Accept: 'application/x-ndjson',
    },
    body: JSON.stringify({ message, project, role }),
    signal,
  });
  if (!res.ok) {
    let data: unknown;
    try {
      data = await res.json();
    } catch {
      data = await res.text();
    }
    throw new BridgeApiError(res.status, data);
  }
  return res;
}
