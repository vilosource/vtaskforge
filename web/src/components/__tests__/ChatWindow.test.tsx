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
        connectionError={null}
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
        connectionError={null}
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
        connectionError={null}
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
        connectionError={null}
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
        connectionError={null}
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
        connectionError={null}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
  });

  it('shows generic error when connectionError is null', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={null}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/Connection failed/i)).toBeInTheDocument();
  });

  it('shows conflict error with username', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={{ type: 'conflict', message: 'Lock held by alice', heldBy: 'alice' }}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/Session held by alice/i)).toBeInTheDocument();
  });

  it('shows forbidden error', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={{ type: 'forbidden', message: 'Not a member' }}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/do not have access/i)).toBeInTheDocument();
  });

  it('shows rate limited error', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={{ type: 'rate_limited', message: 'Rate limit exceeded' }}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/Too many requests/i)).toBeInTheDocument();
  });

  it('shows unavailable error', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={{ type: 'unavailable', message: 'Service unavailable' }}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
  });

  it('shows expired error', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={{ type: 'expired', message: 'Session expired' }}
        onSendMessage={vi.fn()}
      />,
    );
    expect(screen.getByText(/expired/i)).toBeInTheDocument();
  });

  it('shows Retry button when onRetry provided and in error state', () => {
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={{ type: 'network', message: 'Network error' }}
        onSendMessage={vi.fn()}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByTestId('chat-retry')).toBeInTheDocument();
    expect(screen.getByTestId('chat-retry')).toHaveTextContent('Retry');
  });

  it('clicking Retry calls onRetry', async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatWindow
        messages={[]}
        isStreaming={false}
        lockStatus="error"
        connectionError={{ type: 'network', message: 'Network error' }}
        onSendMessage={vi.fn()}
        onRetry={onRetry}
      />,
    );
    await user.click(screen.getByTestId('chat-retry'));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
