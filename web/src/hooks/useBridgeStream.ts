import { useState, useRef, useCallback, useEffect } from 'react';
import type { BridgeStreamEvent } from '../types/chat';
import { streamPrompt } from '../api/bridge';
import { parseNDJSONLine } from '../utils/parseNDJSON';

export interface UseBridgeStreamResult {
  startStream: (message: string, project: string, role: string) => void;
  cancelStream: () => void;
  isStreaming: boolean;
  error: string | null;
}

export function useBridgeStream(
  onEvent: (event: BridgeStreamEvent) => void,
): UseBridgeStreamResult {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    return () => { mountedRef.current = false; };
  }, []);

  const cancelStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const startStream = useCallback(
    (message: string, project: string, role: string) => {
      // Cancel any existing stream
      if (abortRef.current) {
        abortRef.current.abort();
      }

      const controller = new AbortController();
      abortRef.current = controller;

      setError(null);
      setIsStreaming(true);

      (async () => {
        try {
          const response = await streamPrompt(message, project, role, controller.signal);
          const reader = response.body!.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop()!; // keep incomplete line

            for (const line of lines) {
              if (!mountedRef.current) return;
              const event = parseNDJSONLine(line);
              if (event) {
                onEventRef.current(event);
              }
            }
          }

          // Process remaining buffer
          if (buffer.trim() && mountedRef.current) {
            const event = parseNDJSONLine(buffer);
            if (event) {
              onEventRef.current(event);
            }
          }
        } catch (err: unknown) {
          if (err instanceof DOMException && err.name === 'AbortError') {
            // Cancelled — not an error
            return;
          }
          if (mountedRef.current) {
            setError(err instanceof Error ? err.message : 'Stream failed');
          }
        } finally {
          if (abortRef.current === controller && mountedRef.current) {
            setIsStreaming(false);
            abortRef.current = null;
          }
        }
      })();
    },
    [],
  );

  return { startStream, cancelStream, isStreaming, error };
}
