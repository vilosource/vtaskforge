/**
 * vafi-console integration — auth code generation and URL building.
 */

import { apiPost } from './client';

const CONSOLE_BASE_URL =
  (import.meta as any).env?.VITE_CONSOLE_URL || 'https://console.dev.viloforge.com';

interface AuthCodeResponse {
  code: string;
  expires_at: string;
}

interface ConsoleUrlParams {
  role?: string;
  project?: string;
  workplan?: string | number;
  pod?: string;
  command?: string;
  embed?: boolean;
}

/**
 * Generate a single-use authorization code for vafi-console.
 * Requires authenticated vtf session.
 */
export async function generateAuthCode(redirectUri: string): Promise<AuthCodeResponse> {
  return apiPost<AuthCodeResponse>('/v1/auth/code/', { redirect_uri: redirectUri });
}

/**
 * Build a console URL with the given parameters.
 * Does NOT include auth code — call generateAuthCode() separately if auth is enabled.
 */
export function buildConsoleUrl(params: ConsoleUrlParams): string {
  const url = new URL(CONSOLE_BASE_URL);
  if (params.role) url.searchParams.set('role', params.role);
  if (params.project) url.searchParams.set('project', params.project);
  if (params.workplan) url.searchParams.set('workplan', String(params.workplan));
  if (params.pod) url.searchParams.set('pod', params.pod);
  if (params.command) url.searchParams.set('command', params.command);
  if (params.embed) url.searchParams.set('embed', 'true');
  return url.toString();
}

/**
 * Build a console URL with an auth code embedded.
 * Generates the code, appends it to the URL.
 */
export async function buildAuthenticatedConsoleUrl(params: ConsoleUrlParams): Promise<string> {
  const baseUrl = buildConsoleUrl(params);
  try {
    const { code } = await generateAuthCode(baseUrl);
    const url = new URL(baseUrl);
    url.searchParams.set('code', code);
    return url.toString();
  } catch {
    // Auth code generation failed (maybe auth disabled) — return URL without code
    return baseUrl;
  }
}

/**
 * Open vafi-console in a new tab.
 */
export async function openConsoleNewTab(params: ConsoleUrlParams): Promise<void> {
  const url = await buildAuthenticatedConsoleUrl(params);
  window.open(url, '_blank', 'noopener,noreferrer');
}
