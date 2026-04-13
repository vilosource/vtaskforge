import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { ChatWindow } from '../ChatWindow';
import type { ChatMessage } from '../../types/chat';

const sampleMessages: ChatMessage[] = [
  { id: 'msg-1', role: 'user', content: 'What tasks are blocked?', timestamp: 1 },
  {
    id: 'msg-2',
    role: 'assistant',
    content: 'There are 2 blocked tasks.',
    timestamp: 2,
    toolUses: [{ tool: 'vtf_search_tasks', status: 'completed' }],
  },
];

describe('ChatWindow', () => {
  it('renders all messages', () => {
    render(
      <ChatWindow
        messages={sampleMessages}
        isStreaming={false}
        lockStatus="connected"
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText('What tasks are blocked?')).toBeInTheDocument();
    expect(screen.getByText('There are 2 blocked tasks.')).toBeInTheDocument();
  });

  it('renders ChatInput component', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="connected"
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByTestId('chat-input')).toBeInTheDocument();
  });

  it('input is disabled when lockStatus is not connected', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="acquiring"
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByTestId('chat-input')).toBeDisabled();
  });

  it('input calls onSendMessage', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="connected"
        onSendMessage={onSend}
      />,
    );

    await user.type(screen.getByTestId('chat-input'), 'Hello{Enter}');
    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  it('shows empty state when no messages', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="connected"
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByTestId('chat-empty-state')).toBeInTheDocument();
  });

  it('shows connecting indicator when acquiring', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="acquiring"
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
  });

  it('shows error indicator when lockStatus is error', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/Connection failed/i)).toBeInTheDocument();
  });
});
