import type { BridgeStreamEvent } from '../types/chat';

const KNOWN_EVENT_TYPES = new Set([
  'session_start', 'text_delta', 'tool_use', 'agent_event', 'result', 'error',
]);

/**
 * Parses a single line of NDJSON text into a BridgeStreamEvent.
 * Returns null for empty/whitespace lines (keepalives) or unknown event types.
 * Throws SyntaxError on malformed JSON.
 */
export function parseNDJSONLine(line: string): BridgeStreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== 'object' || !('type' in parsed)) {
    console.warn('NDJSON event missing type field:', parsed);
    return null;
  }
  if (!KNOWN_EVENT_TYPES.has(parsed.type)) {
    console.warn('Unknown NDJSON event type:', parsed.type);
    return null;
  }
  return parsed as BridgeStreamEvent;
}
