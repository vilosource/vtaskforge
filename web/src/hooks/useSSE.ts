import { useEffect, useRef, useState } from 'react';

export type SSEStatus = 'connected' | 'reconnecting' | 'disconnected';

interface UseSSEOptions {
  url: string;
  onEvent: (event: MessageEvent) => void;
  enabled?: boolean;
}

const EVENT_TYPES = [
  'task.status_changed',
  'task.claimed',
  'task.unclaimed',
  'task.completed',
  'task.created',
  'task.updated',
  'task.failed',
  'task.blocked',
  'task.unblocked',
];

export function useSSE({ url, onEvent, enabled = true }: UseSSEOptions) {
  const [status, setStatus] = useState<SSEStatus>('disconnected');
  const eventSourceRef = useRef<EventSource | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  // Use a ref so onEvent changes don't re-trigger the effect
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled) return;

    let sseUrl = url;
    if (lastEventIdRef.current) {
      const separator = url.includes('?') ? '&' : '?';
      sseUrl = `${url}${separator}lastEventId=${lastEventIdRef.current}`;
    }

    const es = new EventSource(sseUrl, { withCredentials: true });
    eventSourceRef.current = es;

    es.onopen = () => setStatus('connected');

    es.onerror = () => {
      setStatus('reconnecting');
      // EventSource auto-reconnects — browser handles backoff
    };

    EVENT_TYPES.forEach((type) => {
      es.addEventListener(type, (event: MessageEvent) => {
        lastEventIdRef.current = event.lastEventId;
        onEventRef.current(event);
      });
    });

    return () => {
      es.close();
      eventSourceRef.current = null;
      setStatus('disconnected');
    };
  }, [url, enabled]);

  return { status };
}
