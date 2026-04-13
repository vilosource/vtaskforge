import { useState, useRef, useCallback } from 'react';
import type { BridgeStreamEvent } from '../types/chat';
import { streamPrompt } from '../api/bridge';
import { parseNDJSONLine } from '../utils/parseNDJSON';

export interface UseBridgeStreamResult {
  startStream: (message: string, project: string, role: string) => void;
  cancelStream: () => void;
  isStreaming: boolean;
  events: BridgeStreamEvent[];
  error: string | null;
}

export function useBridgeStream(): UseBridgeStreamResult {
  const [isStreaming, setIsStreaming] = useState(false);
  const [events, setEvents] = useState<BridgeStreamEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

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

      setEvents([]);
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
              const event = parseNDJSONLine(line);
              if (event) {
                setEvents((prev) => [...prev, event]);
              }
            }
          }

          // Process remaining buffer
          if (buffer.trim()) {
            const event = parseNDJSONLine(buffer);
            if (event) {
              setEvents((prev) => [...prev, event]);
            }
          }
        } catch (err: unknown) {
          if (err instanceof DOMException && err.name === 'AbortError') {
            // Cancelled — not an error
            return;
          }
          setError(err instanceof Error ? err.message : 'Stream failed');
        } finally {
          if (abortRef.current === controller) {
            setIsStreaming(false);
            abortRef.current = null;
          }
        }
      })();
    },
    [],
  );

  return { startStream, cancelStream, isStreaming, events, error };
}
