import { useRef, useEffect } from 'react';
import type { ChatMessage as ChatMessageType, LockStatus } from '../types/chat';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';

interface ChatWindowProps {
  messages: ChatMessageType[];
  isStreaming: boolean;
  lockStatus: LockStatus;
  onSendMessage: (content: string) => void;
}

export function ChatWindow({ messages, isStreaming, lockStatus, onSendMessage }: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
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
          <div className="flex items-center justify-center py-8 text-sm text-error">
            <span className="material-symbols-outlined mr-2 text-lg">error</span>
            Connection failed. Please try again.
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
      </div>

      {/* Input */}
      <ChatInput
        onSend={onSendMessage}
        disabled={!isConnected}
        isStreaming={isStreaming}
      />
    </div>
  );
}
