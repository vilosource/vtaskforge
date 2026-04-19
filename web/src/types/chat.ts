// ---- Connection error types ----

export type ConnectionErrorType = 'conflict' | 'forbidden' | 'rate_limited' | 'unavailable' | 'expired' | 'network';

export interface ConnectionError {
  type: ConnectionErrorType;
  message: string;
  heldBy?: string;
}

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

export interface ProjectRef {
  id: string;
  name: string;
}

// Phase 9: a prior-session turn retrieved from GET /v1/sessions/history.
// `username` is null for assistant messages and for user messages whose
// session predates Pre-Phase 0a (no SessionRecord was written).
export interface PriorTurn {
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
  session_id: string;
  username: string | null;
}

export interface ChatWidgetState {
  isOpen: boolean;
  layout: ChatWidgetLayout;
  position: { x: number; y: number };
  size: { width: number; height: number };
  dockWidth: number;
  project: ProjectRef | null;
  sessionId: string | null;
  lockStatus: LockStatus;
  connectionError: ConnectionError | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  // Phase 9 — project-scoped architect history loaded on widget open.
  priorTurns: PriorTurn[];
  priorTurnsLoading: boolean;
}

// ---- Bridge API types ----

export interface BridgeLockResponse {
  session_id: string;
}

export interface BridgeLock {
  session_id: string;
  role: string;
  project: string;
  user: string;
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
