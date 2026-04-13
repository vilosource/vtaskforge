import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { ChatCloseDialog } from '../ChatCloseDialog';

describe('ChatCloseDialog', () => {
  it('renders dialog with title and options', () => {
    render(<ChatCloseDialog onRelease={vi.fn()} onKeepAlive={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByText('Release architect session?')).toBeInTheDocument();
    expect(screen.getByTestId('close-release')).toBeInTheDocument();
    expect(screen.getByTestId('close-keep-alive')).toBeInTheDocument();
    expect(screen.getByTestId('close-cancel')).toBeInTheDocument();
  });

  it('clicking Release calls onRelease', async () => {
    const onRelease = vi.fn();
    const user = userEvent.setup();
    render(<ChatCloseDialog onRelease={onRelease} onKeepAlive={vi.fn()} onCancel={vi.fn()} />);
    await user.click(screen.getByTestId('close-release'));
    expect(onRelease).toHaveBeenCalled();
  });

  it('clicking Keep Alive calls onKeepAlive', async () => {
    const onKeepAlive = vi.fn();
    const user = userEvent.setup();
    render(<ChatCloseDialog onRelease={vi.fn()} onKeepAlive={onKeepAlive} onCancel={vi.fn()} />);
    await user.click(screen.getByTestId('close-keep-alive'));
    expect(onKeepAlive).toHaveBeenCalled();
  });

  it('clicking Cancel calls onCancel', async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(<ChatCloseDialog onRelease={vi.fn()} onKeepAlive={vi.fn()} onCancel={onCancel} />);
    await user.click(screen.getByTestId('close-cancel'));
    expect(onCancel).toHaveBeenCalled();
  });
});
