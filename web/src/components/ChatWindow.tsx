import { useRef, useEffect } from 'react';
import type { ChatMessage as ChatMessageType, LockStatus, ConnectionError } from '../types/chat';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';

interface ChatWindowProps {
  messages: ChatMessageType[];
  isStreaming: boolean;
  lockStatus: LockStatus;
  connectionError: ConnectionError | null;
  onSendMessage: (content: string) => void;
  onStop?: () => void;
  onRetry?: () => void;
}

function errorMessage(connectionError: ConnectionError | null): string {
  if (!connectionError) return 'Connection failed. Please try again.';
  switch (connectionError.type) {
    case 'conflict':
      return connectionError.heldBy
        ? `Session held by ${connectionError.heldBy}. Close their session first.`
        : 'Session held by another user.';
    case 'forbidden':
      return 'You do not have access to this project.';
    case 'rate_limited':
      return 'Too many requests. Please wait a moment.';
    case 'unavailable':
      return 'Bridge service unavailable. The agent may be starting up.';
    case 'expired':
      return 'Session expired. Reconnect to continue.';
    case 'network':
      return connectionError.message || 'Network error. Check your connection.';
    default:
      return 'Connection failed.';
  }
}

export function ChatWindow({ messages, isStreaming, lockStatus, connectionError, onSendMessage, onStop, onRetry }: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const isAtBottom = useRef(true);

  // Track whether user is at the bottom using IntersectionObserver
  useEffect(() => {
    const sentinel = sentinelRef.current;
    const scrollContainer = scrollRef.current;
    if (!sentinel || !scrollContainer) return;
    const observer = new IntersectionObserver(
      ([entry]) => { isAtBottom.current = entry.isIntersecting; },
      { root: scrollContainer, threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  // Auto-scroll only when user is at the bottom
  useEffect(() => {
    if (isAtBottom.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const isConnected = lockStatus === 'connected';

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Message area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3">
        {lockStatus === 'acquiring' && (
          <div className="flex items-center justify-center py-8 text-sm text-on-surface-variant">
            <span className="material-symbols-outlined animate-spin mr-2 text-lg">progress_activity</span>
            Connecting to architect...
          </div>
        )}

        {lockStatus === 'error' && (
          <div data-testid="chat-error" className="flex flex-col items-center justify-center py-8 gap-3">
            <div className="flex items-center text-sm text-error">
              <span className="material-symbols-outlined mr-2 text-lg">error</span>
              {errorMessage(connectionError)}
            </div>
            {onRetry && (
              <button
                data-testid="chat-retry"
                onClick={onRetry}
                className="px-4 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-medium hover:bg-primary/90 transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {isConnected && messages.length === 0 && (
          <div data-testid="chat-empty-state" className="flex flex-col items-center justify-center py-12 text-center">
            <span className="material-symbols-outlined text-4xl text-primary/20 mb-3">chat</span>
            <p className="text-sm font-semibold text-on-surface mb-1">Bridge Chat</p>
            <p className="text-xs text-on-surface-variant max-w-[280px]">
              Your AI-powered project assistant. Ask questions, manage tasks, or get insights.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {isStreaming && (
          <div className="flex justify-start mb-3">
            <div className="px-3 py-2 rounded-xl bg-surface-container-low">
              <span className="inline-block w-2 h-2 bg-primary rounded-full animate-pulse" />
            </div>
          </div>
        )}

        {/* Sentinel for auto-scroll detection */}
        <div ref={sentinelRef} data-testid="scroll-sentinel" className="h-1" />
      </div>

      {/* Input */}
      <ChatInput
        onSend={onSendMessage}
        onStop={onStop}
        disabled={!isConnected}
        isStreaming={isStreaming}
      />
    </div>
  );
}
