import { memo } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import type { ChatMessage as ChatMessageType } from '../types/chat';

interface ChatMessageProps {
  message: ChatMessageType;
}

function ChatMessageInner({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div
      data-testid={isUser ? 'chat-message-user' : 'chat-message-assistant'}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}
    >
      <div
        className={`max-w-[85%] rounded-xl px-3 py-2 ${
          isUser
            ? 'bg-primary-container text-on-primary-container'
            : 'bg-surface-container-low text-on-surface'
        }`}
      >
        {/* Tool use badges */}
        {message.toolUses && message.toolUses.length > 0 && (
          <div data-testid="tool-uses" className="flex flex-wrap gap-1 mb-1">
            {message.toolUses.map((tu, i) => (
              <span
                key={i}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                  tu.status === 'completed'
                    ? 'bg-tertiary-container text-on-tertiary-container'
                    : 'bg-surface-container-high text-on-surface-variant animate-pulse'
                }`}
              >
                {tu.tool}
                {tu.status === 'completed' ? ' \u2713' : ' \u2026'}
              </span>
            ))}
          </div>
        )}

        {/* Message content */}
        {isUser ? (
          <div className="text-sm whitespace-pre-wrap break-words">
            {message.content}
          </div>
        ) : (
          <div className="text-sm prose prose-sm max-w-none break-words prose-p:my-1 prose-pre:my-2 prose-pre:bg-surface-container-high prose-pre:rounded-lg prose-pre:p-3 prose-code:text-xs prose-headings:text-on-surface">
            <Markdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeString = String(children).replace(/\n$/, '');
                  return match ? (
                    <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div">
                      {codeString}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>{children}</code>
                  );
                },
              }}
            >
              {message.content}
            </Markdown>
          </div>
        )}
      </div>
    </div>
  );
}

// Memoize to prevent re-parsing markdown on every stream chunk for unchanged messages
export const ChatMessage = memo(ChatMessageInner);
