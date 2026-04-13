import { useState, useCallback } from 'react';
import TextareaAutosize from 'react-textarea-autosize';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
  isStreaming: boolean;
}

export function ChatInput({ onSend, disabled, isStreaming }: ChatInputProps) {
  const [value, setValue] = useState('');

  const canSend = value.trim().length > 0 && !disabled && !isStreaming;

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isStreaming) return;
    onSend(trimmed);
    setValue('');
  }, [value, disabled, isStreaming, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  return (
    <div className="flex items-end gap-2 p-3 bg-surface-container-lowest">
      <TextareaAutosize
        data-testid="chat-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about this project..."
        disabled={disabled}
        minRows={1}
        maxRows={6}
        className="flex-1 resize-none rounded-md bg-surface-container-low px-3 py-2 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-2 focus:ring-primary/40"
      />
      <button
        data-testid="chat-send"
        onClick={handleSend}
        disabled={!canSend}
        className="rounded-full bg-primary px-3 py-2 text-sm font-medium text-on-primary disabled:opacity-40"
      >
        {isStreaming ? 'Stop' : 'Send'}
      </button>
    </div>
  );
}
