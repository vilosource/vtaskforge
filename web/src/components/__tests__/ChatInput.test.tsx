import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { ChatInput } from '../ChatInput';

describe('ChatInput', () => {
  it('renders textarea and send button', () => {
    render(<ChatInput onSend={vi.fn()} disabled={false} isStreaming={false} />);
    expect(screen.getByTestId('chat-input')).toBeInTheDocument();
    expect(screen.getByTestId('chat-send')).toBeInTheDocument();
  });

  it('send button disabled when textarea empty', () => {
    render(<ChatInput onSend={vi.fn()} disabled={false} isStreaming={false} />);
    expect(screen.getByTestId('chat-send')).toBeDisabled();
  });

  it('send button disabled when disabled prop true', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={vi.fn()} disabled={true} isStreaming={false} />);

    await user.type(screen.getByTestId('chat-input'), 'hello');
    expect(screen.getByTestId('chat-send')).toBeDisabled();
  });

  it('typing updates textarea value', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={vi.fn()} disabled={false} isStreaming={false} />);

    const textarea = screen.getByTestId('chat-input');
    await user.type(textarea, 'Hello agent');
    expect(textarea).toHaveValue('Hello agent');
  });

  it('Enter key calls onSend with message text', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} disabled={false} isStreaming={false} />);

    const textarea = screen.getByTestId('chat-input');
    await user.type(textarea, 'Hello{Enter}');
    expect(onSend).toHaveBeenCalledWith('Hello');
  });

  it('Enter key clears textarea after send', async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={vi.fn()} disabled={false} isStreaming={false} />);

    const textarea = screen.getByTestId('chat-input');
    await user.type(textarea, 'Hello{Enter}');
    expect(textarea).toHaveValue('');
  });

  it('Shift+Enter does not send, inserts newline', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} disabled={false} isStreaming={false} />);

    const textarea = screen.getByTestId('chat-input');
    await user.type(textarea, 'line1{Shift>}{Enter}{/Shift}line2');
    expect(onSend).not.toHaveBeenCalled();
    expect(textarea).toHaveValue('line1\nline2');
  });

  it('send button disabled during streaming', () => {
    render(<ChatInput onSend={vi.fn()} disabled={false} isStreaming={true} />);
    expect(screen.getByTestId('chat-send')).toBeDisabled();
  });

  it('clicking send button calls onSend', async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} disabled={false} isStreaming={false} />);

    const textarea = screen.getByTestId('chat-input');
    await user.type(textarea, 'Click send');

    // Button should now be enabled
    const sendBtn = screen.getByTestId('chat-send');
    expect(sendBtn).not.toBeDisabled();
    await user.click(sendBtn);
    expect(onSend).toHaveBeenCalledWith('Click send');
  });
});
