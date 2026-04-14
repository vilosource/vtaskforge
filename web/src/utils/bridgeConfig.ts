// Single source of truth for bridge API URL.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const BRIDGE_URL = ((globalThis as any).__BRIDGE_URL as string) || 'https://bridge.dev.viloforge.com';
