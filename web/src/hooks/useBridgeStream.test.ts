import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useBridgeStream } from './useBridgeStream';
import type { BridgeStreamEvent } from '../types/chat';

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

  it('initial state: not streaming, no error', () => {
    const onEvent = vi.fn();
    const { result } = renderHook(() => useBridgeStream(onEvent));
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('startStream calls streamPrompt with correct args', async () => {
    const response = mockStreamResponse([]);
    mockStreamPrompt.mockResolvedValueOnce(response);
    const onEvent = vi.fn();

    const { result } = renderHook(() => useBridgeStream(onEvent));

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

  it('calls onEvent for each parsed event', async () => {
    const lines = [
      '{"type":"session_start","session_id":"s1"}',
      '{"type":"text_delta","text":"Hi"}',
      '{"type":"result"}',
    ];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines));
    const onEvent = vi.fn();

    const { result } = renderHook(() => useBridgeStream(onEvent));

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(onEvent).toHaveBeenCalledTimes(3);
    expect(onEvent).toHaveBeenNthCalledWith(1, { type: 'session_start', session_id: 's1' });
    expect(onEvent).toHaveBeenNthCalledWith(2, { type: 'text_delta', text: 'Hi' });
    expect(onEvent).toHaveBeenNthCalledWith(3, { type: 'result' });
  });

  it('isStreaming is true while stream is active', async () => {
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

    const onEvent = vi.fn();
    const { result } = renderHook(() => useBridgeStream(onEvent));

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    expect(result.current.isStreaming).toBe(true);

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

    const onEvent = vi.fn();
    const { result } = renderHook(() => useBridgeStream(onEvent));

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

    resolve!();
  });

  it('sets error when streamPrompt rejects', async () => {
    mockStreamPrompt.mockRejectedValueOnce(new Error('Network error'));
    const onEvent = vi.fn();

    const { result } = renderHook(() => useBridgeStream(onEvent));

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    await vi.waitFor(() => {
      expect(result.current.error).toBe('Network error');
    });
    expect(result.current.isStreaming).toBe(false);
    expect(onEvent).not.toHaveBeenCalled();
  });

  it('passes error events through onEvent', async () => {
    const lines = [
      '{"type":"error","message":"Session expired"}',
    ];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines));
    const onEvent = vi.fn();

    const { result } = renderHook(() => useBridgeStream(onEvent));

    await act(async () => {
      result.current.startStream('hello', 'proj', 'architect');
    });

    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(onEvent).toHaveBeenCalledWith({ type: 'error', message: 'Session expired' });
  });

  it('new startStream cancels previous stream', async () => {
    const lines1 = ['{"type":"text_delta","text":"first"}'];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines1));
    const onEvent = vi.fn();

    const { result } = renderHook(() => useBridgeStream(onEvent));

    await act(async () => {
      result.current.startStream('msg1', 'proj', 'architect');
    });

    const lines2 = ['{"type":"text_delta","text":"second"}', '{"type":"result"}'];
    mockStreamPrompt.mockResolvedValueOnce(mockStreamResponse(lines2));

    await act(async () => {
      result.current.startStream('msg2', 'proj', 'architect');
    });

    await vi.waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    // Should have called onEvent with second stream's events
    const textEvents = onEvent.mock.calls
      .filter((args) => (args[0] as BridgeStreamEvent).type === 'text_delta')
      .map((args) => ((args[0] as BridgeStreamEvent) as { type: string; text: string }).text);
    expect(textEvents).toContain('second');
    expect(mockStreamPrompt).toHaveBeenCalledTimes(2);
  });
});
