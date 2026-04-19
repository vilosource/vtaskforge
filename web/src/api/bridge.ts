import type { BridgeLock, BridgeLockResponse, ConnectionError } from '../types/chat';
import { BRIDGE_URL } from '../utils/bridgeConfig';

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

function extractDetail(data: unknown): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    return String((data as { detail: string }).detail);
  }
  return '';
}

function extractHeldBy(detail: string): string | undefined {
  const match = detail.match(/^Lock held by (.+)$/);
  return match ? match[1] : undefined;
}

export function classifyBridgeError(err: unknown): ConnectionError {
  if (err instanceof BridgeApiError) {
    const detail = extractDetail(err.data);
    switch (err.status) {
      case 409:
        return {
          type: 'conflict',
          message: detail || 'Session held by another user.',
          heldBy: extractHeldBy(detail),
        };
      case 403:
        return { type: 'forbidden', message: detail || 'You do not have access to this project.' };
      case 429:
        return { type: 'rate_limited', message: 'Too many requests. Please wait a moment.' };
      case 503:
        return { type: 'unavailable', message: detail || 'Bridge service unavailable.' };
      default:
        return { type: 'network', message: detail || `Bridge error (${err.status}).` };
    }
  }
  if (err instanceof Error) {
    return { type: 'network', message: err.message || 'Network error. Check your connection.' };
  }
  return { type: 'network', message: 'Connection failed.' };
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


// Phase 9: project-scoped architect conversation history.
// Messages include `username` on user turns; assistant turns have null.
export interface PriorTurn {
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
  session_id: string;
  username: string | null;
}

export interface SessionHistoryResponse {
  turns: PriorTurn[];
  truncated: boolean;
}

export async function fetchSessionHistory(
  project: string,
  role: string,
  opts: { limit?: number; maxAgeDays?: number } = {},
): Promise<SessionHistoryResponse> {
  const params = new URLSearchParams({ project, role });
  if (opts.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts.maxAgeDays !== undefined) params.set('max_age_days', String(opts.maxAgeDays));
  const res = await fetch(`${BRIDGE_URL}/v1/sessions/history?${params}`, {
    method: 'GET',
    headers: {
      ...authHeaders(),
      Accept: 'application/json',
    },
  });
  return handleResponse<SessionHistoryResponse>(res);
}
