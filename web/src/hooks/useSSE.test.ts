import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSSE } from './useSSE';

// Minimal EventSource mock
class MockEventSource {
  static instances: MockEventSource[] = [];

  url: string;
  withCredentials: boolean;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState = 0;

  private listeners: Map<string, ((event: MessageEvent) => void)[]> = new Map();

  constructor(url: string, options?: EventSourceInit) {
    this.url = url;
    this.withCredentials = options?.withCredentials ?? false;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (event: MessageEvent) => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)!.push(handler);
  }

  removeEventListener(type: string, handler: (event: MessageEvent) => void) {
    const handlers = this.listeners.get(type) ?? [];
    const idx = handlers.indexOf(handler);
    if (idx !== -1) handlers.splice(idx, 1);
  }

  close = vi.fn(() => {
    this.readyState = 2;
  });

  /** Test helper: simulate the connection opening */
  simulateOpen() {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }

  /** Test helper: simulate an error */
  simulateError() {
    this.onerror?.(new Event('error'));
  }

  /** Test helper: dispatch a named event */
  simulateEvent(type: string, data: unknown, lastEventId = '') {
    const handlers = this.listeners.get(type) ?? [];
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    Object.defineProperty(event, 'lastEventId', { value: lastEventId, configurable: true });
    handlers.forEach((h) => h(event));
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal('EventSource', MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useSSE', () => {
  it('creates EventSource with withCredentials: true', () => {
    renderHook(() => useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent: vi.fn() }));
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].withCredentials).toBe(true);
  });

  it('creates EventSource with the provided URL', () => {
    renderHook(() => useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent: vi.fn() }));
    expect(MockEventSource.instances[0].url).toBe('/v1/events/stream/?workplan=wp-1');
  });

  it('status changes to connected on open', () => {
    const { result } = renderHook(() =>
      useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent: vi.fn() }),
    );

    expect(result.current.status).toBe('disconnected');

    act(() => {
      MockEventSource.instances[0].simulateOpen();
    });

    expect(result.current.status).toBe('connected');
  });

  it('status changes to reconnecting on error', () => {
    const { result } = renderHook(() =>
      useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent: vi.fn() }),
    );

    act(() => {
      MockEventSource.instances[0].simulateOpen();
    });
    expect(result.current.status).toBe('connected');

    act(() => {
      MockEventSource.instances[0].simulateError();
    });
    expect(result.current.status).toBe('reconnecting');
  });

  it('calls onEvent when a task.status_changed event is received', () => {
    const onEvent = vi.fn();
    renderHook(() => useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent }));

    act(() => {
      MockEventSource.instances[0].simulateEvent('task.status_changed', {
        task_id: 'task-1',
        event_type: 'task.status_changed',
      });
    });

    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent.mock.calls[0][0]).toBeInstanceOf(MessageEvent);
  });

  it('calls onEvent when a task.claimed event is received', () => {
    const onEvent = vi.fn();
    renderHook(() => useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent }));

    act(() => {
      MockEventSource.instances[0].simulateEvent('task.claimed', { task_id: 'task-2' });
    });

    expect(onEvent).toHaveBeenCalledTimes(1);
  });

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() =>
      useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent: vi.fn() }),
    );

    const es = MockEventSource.instances[0];
    unmount();
    expect(es.close).toHaveBeenCalled();
  });

  it('does not create EventSource when enabled is false', () => {
    renderHook(() =>
      useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent: vi.fn(), enabled: false }),
    );
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it('returns disconnected status when enabled is false', () => {
    const { result } = renderHook(() =>
      useSSE({ url: '/v1/events/stream/?workplan=wp-1', onEvent: vi.fn(), enabled: false }),
    );
    expect(result.current.status).toBe('disconnected');
  });
});
