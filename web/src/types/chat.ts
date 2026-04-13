// ---- Value types ----

export interface ToolUse {
  tool: string;
  status: 'started' | 'completed';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  toolUses?: ToolUse[];
}

// ---- Widget state types ----

export type ChatWidgetLayout = 'floating' | 'docked' | 'minimized';

export type LockStatus = 'disconnected' | 'acquiring' | 'connected' | 'error';

export interface ChatWidgetState {
  isOpen: boolean;
  layout: ChatWidgetLayout;
  position: { x: number; y: number };
  size: { width: number; height: number };
  dockWidth: number;
  project: string | null;
  sessionId: string | null;
  lockStatus: LockStatus;
  messages: ChatMessage[];
  isStreaming: boolean;
}

// ---- Bridge API types ----

export interface BridgeLockResponse {
  session_id: string;
}

export interface BridgeLock {
  session_id: string;
  role: string;
  project: string;
  user?: string;
}

// ---- Stream event discriminated union ----

export interface SessionStartEvent {
  type: 'session_start';
  session_id: string;
}

export interface TextDeltaEvent {
  type: 'text_delta';
  text: string;
}

export interface ToolUseEvent {
  type: 'tool_use';
  tool: string;
  status: 'started' | 'completed';
}

export interface AgentEventEvent {
  type: 'agent_event';
  [key: string]: unknown;
}

export interface ResultEvent {
  type: 'result';
  message?: string;
  token_usage?: { input: number; output: number };
}

export interface ErrorEvent {
  type: 'error';
  message: string;
}

export type BridgeStreamEvent =
  | SessionStartEvent
  | TextDeltaEvent
  | ToolUseEvent
  | AgentEventEvent
  | ResultEvent
  | ErrorEvent;
