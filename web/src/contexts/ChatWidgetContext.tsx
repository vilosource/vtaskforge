import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import type {
  ChatWidgetState,
  ChatWidgetLayout,
  ChatMessage,
  ToolUse,
} from '../types/chat';
import { checkLock, acquireLock, releaseLock } from '../api/bridge';
import { useBridgeStream } from '../hooks/useBridgeStream';

// ---- Context value interface ----

interface ChatWidgetActions {
  open: (project: string) => void;
  close: () => void;
  releaseAndClose: () => void;
  keepAliveAndMinimize: () => void;
  minimize: () => void;
  restore: () => void;
  dock: () => void;
  float: () => void;
  setPosition: (pos: { x: number; y: number }) => void;
  setSize: (size: { width: number; height: number }) => void;
  setDockWidth: (width: number) => void;
  sendMessage: (content: string) => void;
  clearMessages: () => void;
}

type ChatWidgetContextValue = ChatWidgetState & ChatWidgetActions;

// ---- Constants ----

const STORAGE_KEY = 'vtf_chat_widget';
const ROLE = 'architect';

const DEFAULT_STATE: ChatWidgetState = {
  isOpen: false,
  layout: 'floating',
  position: { x: 100, y: 100 },
  size: { width: 480, height: 600 },
  dockWidth: 420,
  project: null,
  sessionId: null,
  lockStatus: 'disconnected',
  messages: [],
  isStreaming: false,
};

// ---- Persistence ----

interface PersistedLayout {
  layout?: ChatWidgetLayout;
  position?: { x: number; y: number };
  size?: { width: number; height: number };
  dockWidth?: number;
}

function loadPersistedLayout(): PersistedLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function persistLayout(state: PersistedLayout) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage may be unavailable
  }
}

// ---- Message persistence ----

function messagesKey(project: string, sessionId: string): string {
  return `vtf_chat_messages_${project}_${sessionId}`;
}

function persistMessages(project: string | null, sessionId: string | null, messages: ChatMessage[]) {
  if (!project || !sessionId) return;
  try {
    localStorage.setItem(messagesKey(project, sessionId), JSON.stringify(messages));
  } catch {
    // localStorage may be unavailable or full
  }
}

function loadMessages(project: string, sessionId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(messagesKey(project, sessionId));
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function clearPersistedMessages(project: string | null, sessionId: string | null) {
  if (!project || !sessionId) return;
  try {
    localStorage.removeItem(messagesKey(project, sessionId));
  } catch {
    // ignore
  }
}

// ---- Context ----

const ChatWidgetContext = createContext<ChatWidgetContextValue>({
  ...DEFAULT_STATE,
  open: () => {},
  close: () => {},
  releaseAndClose: () => {},
  keepAliveAndMinimize: () => {},
  minimize: () => {},
  restore: () => {},
  dock: () => {},
  float: () => {},
  setPosition: () => {},
  setSize: () => {},
  setDockWidth: () => {},
  sendMessage: () => {},
  clearMessages: () => {},
});

// ---- Unique ID generator ----

let msgCounter = 0;
function nextMsgId(): string {
  return `msg-${Date.now()}-${++msgCounter}`;
}

// ---- Provider ----

export function ChatWidgetProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ChatWidgetState>(() => {
    const persisted = loadPersistedLayout();
    return {
      ...DEFAULT_STATE,
      layout: persisted.layout ?? DEFAULT_STATE.layout,
      position: persisted.position ?? DEFAULT_STATE.position,
      size: persisted.size ?? DEFAULT_STATE.size,
      dockWidth: persisted.dockWidth ?? DEFAULT_STATE.dockWidth,
    };
  });

  const stream = useBridgeStream();
  const streamRef = useRef(stream);
  streamRef.current = stream;

  // Persist layout preferences
  useEffect(() => {
    persistLayout({
      layout: state.layout,
      position: state.position,
      size: state.size,
      dockWidth: state.dockWidth,
    });
  }, [state.layout, state.position, state.size, state.dockWidth]);

  // Persist messages to localStorage
  useEffect(() => {
    if (state.messages.length > 0) {
      persistMessages(state.project, state.sessionId, state.messages);
    }
  }, [state.messages, state.project, state.sessionId]);

  // Best-effort lock release on tab close
  useEffect(() => {
    const handleBeforeUnload = () => {
      const { project, lockStatus } = stateRef.current;
      if (lockStatus === 'connected' && project) {
        const token = localStorage.getItem('vtf_token');
        if (token) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const bridgeUrl = ((globalThis as any).__BRIDGE_URL as string) || 'https://bridge.dev.viloforge.com';
          fetch(`${bridgeUrl}/v1/lock`, {
            method: 'DELETE',
            headers: {
              Authorization: `Token ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ project, role: ROLE }),
            keepalive: true,
          });
        }
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // Process stream events into messages
  const lastProcessedIndex = useRef(0);

  useEffect(() => {
    const { events } = stream;
    if (events.length <= lastProcessedIndex.current) return;

    const newEvents = events.slice(lastProcessedIndex.current);
    lastProcessedIndex.current = events.length;

    setState((prev) => {
      let messages = [...prev.messages];
      let lastAssistant = messages.length > 0 && messages[messages.length - 1].role === 'assistant'
        ? { ...messages[messages.length - 1] }
        : null;

      for (const event of newEvents) {
        switch (event.type) {
          case 'text_delta': {
            if (!lastAssistant) {
              lastAssistant = {
                id: nextMsgId(),
                role: 'assistant',
                content: '',
                timestamp: Date.now(),
                toolUses: [],
              };
              messages = [...messages, lastAssistant];
            }
            lastAssistant = { ...lastAssistant, content: lastAssistant.content + event.text };
            messages = [...messages.slice(0, -1), lastAssistant];
            break;
          }
          case 'tool_use': {
            if (!lastAssistant) {
              lastAssistant = {
                id: nextMsgId(),
                role: 'assistant',
                content: '',
                timestamp: Date.now(),
                toolUses: [],
              };
              messages = [...messages, lastAssistant];
            }
            const toolUse: ToolUse = { tool: event.tool, status: event.status };
            lastAssistant = {
              ...lastAssistant,
              toolUses: [...(lastAssistant.toolUses || []), toolUse],
            };
            messages = [...messages.slice(0, -1), lastAssistant];
            break;
          }
          case 'session_start':
          case 'agent_event':
          case 'result':
          case 'error':
            // These don't modify messages directly
            break;
        }
      }

      return { ...prev, messages, isStreaming: stream.isStreaming };
    });
  }, [stream.events, stream.isStreaming]);

  // Sync isStreaming from stream hook
  useEffect(() => {
    setState((prev) => {
      if (prev.isStreaming !== stream.isStreaming) {
        return { ...prev, isStreaming: stream.isStreaming };
      }
      return prev;
    });
  }, [stream.isStreaming]);

  // ---- Layout actions ----

  const minimize = useCallback(() => {
    setState((prev) => ({ ...prev, layout: 'minimized' }));
  }, []);

  const restore = useCallback(() => {
    setState((prev) => ({
      ...prev,
      layout: prev.layout === 'minimized' ? 'floating' : prev.layout,
    }));
  }, []);

  const dock = useCallback(() => {
    setState((prev) => ({ ...prev, layout: 'docked' }));
  }, []);

  const float = useCallback(() => {
    setState((prev) => ({ ...prev, layout: 'floating' }));
  }, []);

  const setPosition = useCallback((pos: { x: number; y: number }) => {
    setState((prev) => ({ ...prev, position: pos }));
  }, []);

  const setSize = useCallback((size: { width: number; height: number }) => {
    setState((prev) => ({ ...prev, size }));
  }, []);

  const setDockWidth = useCallback((dockWidth: number) => {
    setState((prev) => ({ ...prev, dockWidth }));
  }, []);

  // ---- State ref for callbacks that need current state ----

  const stateRef = useRef(state);
  stateRef.current = state;

  // ---- Session lifecycle ----

  const acquireSession = useCallback(async (project: string) => {
    setState((prev) => ({ ...prev, lockStatus: 'acquiring' }));

    try {
      const locks = await checkLock(project, ROLE);
      if (locks.length > 0) {
        // Reconnect to existing lock — restore messages from localStorage
        const sessionId = locks[0].session_id;
        const restoredMessages = loadMessages(project, sessionId);
        setState((prev) => ({
          ...prev,
          sessionId,
          lockStatus: 'connected',
          messages: restoredMessages,
        }));
      } else {
        // Acquire new lock
        const lock = await acquireLock(project, ROLE);
        setState((prev) => ({
          ...prev,
          sessionId: lock.session_id,
          lockStatus: 'connected',
        }));
      }
    } catch {
      setState((prev) => ({
        ...prev,
        lockStatus: 'error',
        sessionId: null,
      }));
    }
  }, []);

  const open = useCallback((project: string) => {
    setState((prev) => ({ ...prev, isOpen: true, project }));
    acquireSession(project);
  }, [acquireSession]);

  // Release lock, clear everything, close widget
  const releaseAndClose = useCallback(async () => {
    const { project, lockStatus, sessionId } = stateRef.current;
    if (lockStatus === 'connected' && project) {
      try {
        await releaseLock(project, ROLE);
      } catch {
        // Best effort release
      }
    }
    // Clear persisted messages for this session
    clearPersistedMessages(project, sessionId);
    streamRef.current.cancelStream();
    lastProcessedIndex.current = 0;
    setState((prev) => ({
      ...prev,
      isOpen: false,
      project: null,
      sessionId: null,
      lockStatus: 'disconnected',
      messages: [],
      isStreaming: false,
    }));
  }, []);

  // Keep lock alive, just minimize the widget
  const keepAliveAndMinimize = useCallback(() => {
    setState((prev) => ({ ...prev, layout: 'minimized' }));
  }, []);

  // Default close — same as releaseAndClose (used when lockStatus is not connected)
  const close = useCallback(async () => {
    await releaseAndClose();
  }, [releaseAndClose]);

  // ---- Chat actions ----

  const sendMessage = useCallback((content: string) => {
    const userMessage: ChatMessage = {
      id: nextMsgId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };

    setState((prev) => {
      if (!prev.project) return prev;
      return { ...prev, messages: [...prev.messages, userMessage] };
    });

    const { project } = stateRef.current;
    if (project) {
      lastProcessedIndex.current = 0;
      streamRef.current.startStream(content, project, ROLE);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setState((prev) => ({ ...prev, messages: [] }));
    lastProcessedIndex.current = 0;
  }, []);

  // ---- Value ----

  const value: ChatWidgetContextValue = {
    ...state,
    open,
    close,
    releaseAndClose,
    keepAliveAndMinimize,
    minimize,
    restore,
    dock,
    float,
    setPosition,
    setSize,
    setDockWidth,
    sendMessage,
    clearMessages,
  };

  return (
    <ChatWidgetContext.Provider value={value}>
      {children}
    </ChatWidgetContext.Provider>
  );
}

export function useChatWidget(): ChatWidgetContextValue {
  return useContext(ChatWidgetContext);
}
