import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ChatWidgetProvider, useChatWidget } from '../ChatWidgetContext';

// Mock bridge API — import real classifyBridgeError since it's pure logic
vi.mock('../../api/bridge', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/bridge')>();
  return {
    ...actual,
    checkLock: vi.fn(),
    acquireLock: vi.fn(),
    releaseLock: vi.fn(),
    // Phase 9: default to empty history so unrelated tests aren't affected.
    fetchSessionHistory: vi.fn().mockResolvedValue({ turns: [], truncated: false }),
  };
});

// Mock stream hook — captures the onEvent callback for testing
let capturedOnEvent: ((event: import('../../types/chat').BridgeStreamEvent) => void) | null = null;

vi.mock('../../hooks/useBridgeStream', () => ({
  useBridgeStream: vi.fn((onEvent: (event: import('../../types/chat').BridgeStreamEvent) => void) => {
    capturedOnEvent = onEvent;
    return {
      startStream: vi.fn(),
      cancelStream: vi.fn(),
      isStreaming: false,
      error: null,
    };
  }),
}));

// Mock useAuth
vi.mock('../../App', () => ({
  useAuth: vi.fn(() => ({ username: 'admin', authenticated: true, loading: false, isStaff: false, userType: 'human', projects: [] })),
}));

import { checkLock, acquireLock, releaseLock } from '../../api/bridge';
import { useBridgeStream } from '../../hooks/useBridgeStream';

const mockCheckLock = vi.mocked(checkLock);
const mockAcquireLock = vi.mocked(acquireLock);
const mockReleaseLock = vi.mocked(releaseLock);
const mockUseBridgeStream = vi.mocked(useBridgeStream);

function wrapper({ children }: { children: React.ReactNode }) {
  return <ChatWidgetProvider>{children}</ChatWidgetProvider>;
}

describe('ChatWidgetContext', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    capturedOnEvent = null;
    mockUseBridgeStream.mockImplementation((onEvent: (event: import('../../types/chat').BridgeStreamEvent) => void) => {
      capturedOnEvent = onEvent;
      return {
        startStream: vi.fn(),
        cancelStream: vi.fn(),
        isStreaming: false,
        error: null,
      };
    });
  });

  // ---- Initial state ----

  it('initial state is closed with no session', () => {
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    expect(result.current.isOpen).toBe(false);
    expect(result.current.project).toBeNull();
    expect(result.current.sessionId).toBeNull();
    expect(result.current.lockStatus).toBe('disconnected');
    expect(result.current.messages).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
  });

  // ---- Layout actions ----

  it('layout defaults to floating', () => {
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    expect(result.current.layout).toBe('floating');
  });

  it('dock() changes layout to docked', () => {
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    act(() => { result.current.dock(); });
    expect(result.current.layout).toBe('docked');
  });

  it('minimize() changes layout to minimized', () => {
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    act(() => { result.current.minimize(); });
    expect(result.current.layout).toBe('minimized');
  });

  it('restore() from minimized returns to floating', () => {
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    act(() => { result.current.minimize(); });
    expect(result.current.layout).toBe('minimized');
    act(() => { result.current.restore(); });
    expect(result.current.layout).toBe('floating');
  });

  it('float() changes layout to floating', () => {
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    act(() => { result.current.dock(); });
    act(() => { result.current.float(); });
    expect(result.current.layout).toBe('floating');
  });

  // ---- localStorage persistence ----

  it('layout persists to localStorage', () => {
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    act(() => { result.current.dock(); });
    const stored = JSON.parse(localStorage.getItem('vtf_chat_widget') ?? '{}');
    expect(stored.layout).toBe('docked');
  });

  it('layout restores from localStorage', () => {
    localStorage.setItem(
      'vtf_chat_widget',
      JSON.stringify({ layout: 'docked', dockWidth: 450 }),
    );
    const { result } = renderHook(() => useChatWidget(), { wrapper });
    expect(result.current.layout).toBe('docked');
    expect(result.current.dockWidth).toBe(450);
  });

  // ---- Open / Close ----

  it('open() sets isOpen and project', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });

    const { result } = renderHook(() => useChatWidget(), { wrapper });
    await act(async () => { result.current.open('my-project'); });
    expect(result.current.isOpen).toBe(true);
    expect(result.current.project).toBe('my-project');
  });

  it('close() clears state', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });
    mockReleaseLock.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useChatWidget(), { wrapper });
    await act(async () => { result.current.open('my-project'); });
    expect(result.current.isOpen).toBe(true);
    expect(result.current.sessionId).toBe('sess-1');

    await act(async () => { result.current.close(); });
    expect(result.current.isOpen).toBe(false);
    expect(result.current.project).toBeNull();
    expect(result.current.sessionId).toBeNull();
    expect(result.current.lockStatus).toBe('disconnected');
  });

  // ---- Session lifecycle ----

  it('open() triggers lock acquisition, transitions lockStatus', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-new' });

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    expect(mockCheckLock).toHaveBeenCalledWith('proj', 'architect');
    expect(mockAcquireLock).toHaveBeenCalledWith('proj', 'architect');
    expect(result.current.lockStatus).toBe('connected');
    expect(result.current.sessionId).toBe('sess-new');
  });

  it('open() reconnects to existing lock', async () => {
    mockCheckLock.mockResolvedValueOnce([
      { session_id: 'sess-existing', role: 'architect', project: 'proj', user: 'admin' },
    ]);

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    expect(mockAcquireLock).not.toHaveBeenCalled();
    expect(result.current.lockStatus).toBe('connected');
    expect(result.current.sessionId).toBe('sess-existing');
  });

  it('open() shows conflict when lock is held by different user', async () => {
    mockCheckLock.mockResolvedValueOnce([
      { session_id: 'sess-other', role: 'architect', project: 'proj', user: 'alice' },
    ]);

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    expect(mockAcquireLock).not.toHaveBeenCalled();
    expect(result.current.lockStatus).toBe('error');
    expect(result.current.connectionError).not.toBeNull();
    expect(result.current.connectionError!.type).toBe('conflict');
    expect(result.current.connectionError!.heldBy).toBe('alice');
  });

  it('open() reconnects when lock is held by same user', async () => {
    mockCheckLock.mockResolvedValueOnce([
      { session_id: 'sess-mine', role: 'architect', project: 'proj', user: 'admin' },
    ]);

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    expect(mockAcquireLock).not.toHaveBeenCalled();
    expect(result.current.lockStatus).toBe('connected');
    expect(result.current.sessionId).toBe('sess-mine');
  });

  it('open() sets error on lock failure', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockRejectedValueOnce(new Error('Lock conflict'));

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    expect(result.current.lockStatus).toBe('error');
    expect(result.current.sessionId).toBeNull();
    expect(result.current.connectionError).not.toBeNull();
    expect(result.current.connectionError!.type).toBe('network');
  });

  it('close() calls releaseLock when connected', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });
    mockReleaseLock.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });
    expect(result.current.lockStatus).toBe('connected');

    await act(async () => { result.current.close(); });
    expect(mockReleaseLock).toHaveBeenCalledWith('proj', 'architect');
  });

  // ---- Messages ----

  it('sendMessage adds user message to messages', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });

    const mockStartStream = vi.fn();
    mockUseBridgeStream.mockImplementation((onEvent) => {
      capturedOnEvent = onEvent;
      return {
        startStream: mockStartStream,
        cancelStream: vi.fn(),
        isStreaming: false,
        error: null,
      };
    });

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });
    act(() => { result.current.sendMessage('Hello agent'); });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].content).toBe('Hello agent');
  });

  it('sendMessage triggers startStream', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });

    const mockStartStream = vi.fn();
    mockUseBridgeStream.mockImplementation((onEvent) => {
      capturedOnEvent = onEvent;
      return {
        startStream: mockStartStream,
        cancelStream: vi.fn(),
        isStreaming: false,
        error: null,
      };
    });

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });
    act(() => { result.current.sendMessage('Hello'); });

    expect(mockStartStream).toHaveBeenCalledWith('Hello', 'proj', 'architect');
  });

  it('clearMessages empties the messages array', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });
    act(() => { result.current.sendMessage('Hello'); });
    expect(result.current.messages).toHaveLength(1);

    act(() => { result.current.clearMessages(); });
    expect(result.current.messages).toEqual([]);
  });

  // ---- Stream event processing (callback-based) ----

  it('text_delta events build assistant message', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    // Simulate stream events via the captured onEvent callback
    act(() => {
      capturedOnEvent!({ type: 'text_delta', text: 'Hello ' });
      capturedOnEvent!({ type: 'text_delta', text: 'world' });
    });

    const assistantMsgs = result.current.messages.filter((m) => m.role === 'assistant');
    expect(assistantMsgs).toHaveLength(1);
    expect(assistantMsgs[0].content).toBe('Hello world');
  });

  it('tool_use events appear on assistant message', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-1' });

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    act(() => {
      capturedOnEvent!({ type: 'tool_use', tool: 'bash', status: 'started' });
      capturedOnEvent!({ type: 'text_delta', text: 'Done' });
      capturedOnEvent!({ type: 'tool_use', tool: 'bash', status: 'completed' });
    });

    const assistantMsgs = result.current.messages.filter((m) => m.role === 'assistant');
    expect(assistantMsgs).toHaveLength(1);
    expect(assistantMsgs[0].toolUses).toEqual([
      { tool: 'bash', status: 'started' },
      { tool: 'bash', status: 'completed' },
    ]);
  });

  // ---- Message persistence ----

  it('messages persist to localStorage when session is connected', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-persist' });

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('my-proj'); });
    act(() => { result.current.sendMessage('Persisted msg'); });

    const key = 'vtf_chat_messages_my-proj_sess-persist';
    const stored = localStorage.getItem(key);
    expect(stored).not.toBeNull();
    const messages = JSON.parse(stored!);
    expect(messages).toHaveLength(1);
    expect(messages[0].content).toBe('Persisted msg');
  });

  it('messages restore from localStorage on open with existing session', async () => {
    // Pre-populate localStorage with messages from a previous session
    const existingMessages = [
      { id: 'old-1', role: 'user', content: 'Previous question', timestamp: 1000 },
      { id: 'old-2', role: 'assistant', content: 'Previous answer', timestamp: 2000 },
    ];
    localStorage.setItem(
      'vtf_chat_messages_proj_sess-existing',
      JSON.stringify(existingMessages),
    );

    mockCheckLock.mockResolvedValueOnce([
      { session_id: 'sess-existing', role: 'architect', project: 'proj', user: 'admin' },
    ]);

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].content).toBe('Previous question');
    expect(result.current.messages[1].content).toBe('Previous answer');
  });

  // ---- beforeunload ----

  it('registers beforeunload handler when connected', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-unload' });

    const addSpy = vi.spyOn(window, 'addEventListener');

    const { result, unmount } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });

    expect(addSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));

    addSpy.mockRestore();
    unmount();
  });

  it('releaseAndClose clears persisted messages', async () => {
    mockCheckLock.mockResolvedValueOnce([]);
    mockAcquireLock.mockResolvedValueOnce({ session_id: 'sess-clear' });
    mockReleaseLock.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useChatWidget(), { wrapper });

    await act(async () => { result.current.open('proj'); });
    act(() => { result.current.sendMessage('Will be cleared'); });

    const key = 'vtf_chat_messages_proj_sess-clear';
    expect(localStorage.getItem(key)).not.toBeNull();

    await act(async () => { result.current.releaseAndClose(); });
    expect(localStorage.getItem(key)).toBeNull();
  });
});
