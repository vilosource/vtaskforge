import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ChatMessage } from '../ChatMessage';
import type { ChatMessage as ChatMessageType } from '../../types/chat';

function makeMessage(overrides: Partial<ChatMessageType> = {}): ChatMessageType {
  return {
    id: 'msg-1',
    role: 'user',
    content: 'Hello world',
    timestamp: Date.now(),
    ...overrides,
  };
}

describe('ChatMessage', () => {
  it('renders user message with correct test id', () => {
    render(<ChatMessage message={makeMessage({ role: 'user' })} />);
    expect(screen.getByTestId('chat-message-user')).toBeInTheDocument();
  });

  it('renders assistant message with correct test id', () => {
    render(<ChatMessage message={makeMessage({ role: 'assistant' })} />);
    expect(screen.getByTestId('chat-message-assistant')).toBeInTheDocument();
  });

  it('displays message content', () => {
    render(<ChatMessage message={makeMessage({ content: 'Test content here' })} />);
    expect(screen.getByText('Test content here')).toBeInTheDocument();
  });

  it('shows tool use badges when toolUses present', () => {
    const msg = makeMessage({
      role: 'assistant',
      toolUses: [
        { tool: 'bash', status: 'completed' },
        { tool: 'edit', status: 'started' },
      ],
    });
    render(<ChatMessage message={msg} />);
    expect(screen.getByText(/bash/)).toBeInTheDocument();
    expect(screen.getByText(/edit/)).toBeInTheDocument();
  });

  it('does not show tool use section when toolUses absent', () => {
    render(<ChatMessage message={makeMessage({ role: 'assistant', toolUses: undefined })} />);
    expect(screen.queryByTestId('tool-uses')).not.toBeInTheDocument();
  });

  it('user message has right-alignment class', () => {
    render(<ChatMessage message={makeMessage({ role: 'user' })} />);
    const el = screen.getByTestId('chat-message-user');
    expect(el.className).toContain('justify-end');
  });

  it('assistant message has left-alignment class', () => {
    render(<ChatMessage message={makeMessage({ role: 'assistant' })} />);
    const el = screen.getByTestId('chat-message-assistant');
    expect(el.className).toContain('justify-start');
  });

  it('assistant message renders markdown bold', () => {
    render(<ChatMessage message={makeMessage({ role: 'assistant', content: 'This is **bold** text' })} />);
    const bold = screen.getByText('bold');
    expect(bold.tagName).toBe('STRONG');
  });

  it('assistant message renders markdown code block', () => {
    render(<ChatMessage message={makeMessage({ role: 'assistant', content: '```\nconst x = 1;\n```' })} />);
    expect(screen.getByText('const x = 1;')).toBeInTheDocument();
  });

  it('user message does NOT render markdown (plain text)', () => {
    render(<ChatMessage message={makeMessage({ role: 'user', content: 'This is **not bold**' })} />);
    // Should show the raw markdown text, not rendered
    expect(screen.getByText('This is **not bold**')).toBeInTheDocument();
  });
});
