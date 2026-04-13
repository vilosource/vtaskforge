import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useBridgeStream } from './useBridgeStream';

// Mock bridge API
vi.mock('../api/bridge', () => ({
  streamPrompt: vi.fn(),
}));

import { streamPrompt } from '../api/bridge';
const mockStreamPrompt = vi.mocked(streamPrompt);

/** Creates a mock ReadableStream that emits the given lines as NDJSON chunks. */
function createMockStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < lines.length) {
        controller.enqueue(encoder.encode(lines[index] + '\n'));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

function mockStreamResponse(lines: string[]): Response {
  return {
    ok: true,
    status: 200,
    body: createMockStream(lines),
  } as unknown as Response;
}

describe('useBridgeStream', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initial state: not streaming, no events, no error', () => {
    const { result } = renderHook(() => useBridgeStream());
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.events).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it('startStream calls streamPrompt with correct args', async () => {
    const response = mockStreamResponse([]);
    mockStreamPrompt.mockResolvedValueOnce(response);

    const { result } = renderHook(() => useBridgeStream());

    await act(async () => {
      result.current.startStream('hello', 'my-proj', 'architect');
    });

    expect(mockStreamPrompt).toHaveBeenCalledWith(
      'hello',
      'my-proj',
      'architect',
      expect.any(AbortSignal),
    );
  });

  it('accumulates events as stream emits lines', async () => {
    const lines = [
      '{"type":"session_start","session_id":"s1"}',
      '{"type":"text_delta","text":"Hi"}',
      '{"type":"result"}',
    ];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines));

    const { result } = renderHook(() => useBridgeStream());

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    // Wait for stream to complete
    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(result.current.events).toHaveLength(3);
    expect(result.current.events[0]).toEqual({ type: 'session_start', session_id: 's1' });
    expect(result.current.events[1]).toEqual({ type: 'text_delta', text: 'Hi' });
    expect(result.current.events[2]).toEqual({ type: 'result' });
  });

  it('isStreaming is true while stream is active', async () => {
    // Use a stream that won't auto-close so we can check isStreaming
    let resolve: () => void;
    const blockingPromise = new Promise<void>((r) => { resolve = r; });

    const stream = new ReadableStream<Uint8Array>({
      async pull(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode('{"type":"text_delta","text":"hi"}\n'));
        await blockingPromise;
        controller.close();
      },
    });

    mockStreamPrompt.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: stream,
    } as unknown as Response);

    const { result } = renderHook(() => useBridgeStream());

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    expect(result.current.isStreaming).toBe(true);

    // Release the stream
    await act(async () => {
      resolve!();
    });

    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });
  });

  it('cancelStream aborts the stream', async () => {
    let resolve: () => void;
    const blockingPromise = new Promise<void>((r) => { resolve = r; });

    const stream = new ReadableStream<Uint8Array>({
      async pull(controller) {
        const encoder = new TextEncoder();
        controller.enqueue(encoder.encode('{"type":"text_delta","text":"hi"}\n'));
        await blockingPromise;
        controller.close();
      },
    });

    mockStreamPrompt.mockResolvedValueOnce({
      ok: true,
      status: 200,
      body: stream,
    } as unknown as Response);

    const { result } = renderHook(() => useBridgeStream());

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    expect(result.current.isStreaming).toBe(true);

    await act(async () => {
      result.current.cancelStream();
    });

    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    // Clean up
    resolve!();
  });

  it('sets error when streamPrompt rejects', async () => {
    mockStreamPrompt.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useBridgeStream());

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    await vi.waitFor(() => {
      expect(result.current.error).toBe('Network error');
    });
    expect(result.current.isStreaming).toBe(false);
  });

  it('sets error from bridge error event', async () => {
    const lines = [
      '{"type":"error","message":"Session expired"}',
    ];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines));

    const { result } = renderHook(() => useBridgeStream());

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]).toEqual({ type: 'error', message: 'Session expired' });
  });

  it('new startStream cancels previous stream', async () => {
    // First stream
    const lines1 = ['{"type":"text_delta","text":"first"}'];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines1));

    const { result } = renderHook(() => useBridgeStream());

    await act(async () => {
      result.current.startStream('msg1', 'proj', 'architect');
    });

    // Second stream (should reset events)
    const lines2 = ['{"type":"text_delta","text":"second"}', '{"type":"result"}'];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines2));

    await act(async () => {
      result.current.startStream('msg2', 'proj', 'architect');
    });

    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    // Should have events from second stream only
    expect(result.current.events.some((e) => e.type === 'text_delta' && 'text' in e && e.text === 'second')).toBe(true);
    expect(mockStreamPrompt).toHaveBeenCalledTimes(2);
  });
});
