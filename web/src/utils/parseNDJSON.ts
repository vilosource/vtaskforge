import type { BridgeStreamEvent } from '../types/chat';

/**
 * Parses a single line of NDJSON text into a BridgeStreamEvent.
 * Returns null for empty/whitespace lines (keepalives).
 * Throws SyntaxError on malformed JSON.
 */
export function parseNDJSONLine(line: string): BridgeStreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  return JSON.parse(trimmed) as BridgeStreamEvent;
}
