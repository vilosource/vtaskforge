import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { ChatTitleBar } from '../ChatTitleBar';
import type { LockStatus, ChatWidgetLayout } from '../../types/chat';

const defaultProps = {
  project: 'test-proj',
  lockStatus: 'connected' as LockStatus,
  layout: 'floating' as ChatWidgetLayout,
  onDock: vi.fn(),
  onFloat: vi.fn(),
  onMinimize: vi.fn(),
  onClose: vi.fn(),
};

describe('ChatTitleBar', () => {
  it('renders project name in title', () => {
    render(<ChatTitleBar {...defaultProps} />);
    expect(screen.getByText(/test-proj/)).toBeInTheDocument();
  });

  it('renders with data-testid', () => {
    render(<ChatTitleBar {...defaultProps} />);
    expect(screen.getByTestId('chat-title-bar')).toBeInTheDocument();
  });

  it('shows green dot when lockStatus is connected', () => {
    render(<ChatTitleBar {...defaultProps} lockStatus="connected" />);
    const dot = screen.getByTestId('lock-status-dot');
    expect(dot.className).toContain('bg-green');
  });

  it('shows yellow dot when lockStatus is acquiring', () => {
    render(<ChatTitleBar {...defaultProps} lockStatus="acquiring" />);
    const dot = screen.getByTestId('lock-status-dot');
    expect(dot.className).toContain('bg-yellow');
  });

  it('shows red dot when lockStatus is error', () => {
    render(<ChatTitleBar {...defaultProps} lockStatus="error" />);
    const dot = screen.getByTestId('lock-status-dot');
    expect(dot.className).toContain('bg-red');
  });

  it('shows gray dot when lockStatus is disconnected', () => {
    render(<ChatTitleBar {...defaultProps} lockStatus="disconnected" />);
    const dot = screen.getByTestId('lock-status-dot');
    expect(dot.className).toContain('bg-gray');
  });

  it('shows dock button when layout is floating', () => {
    render(<ChatTitleBar {...defaultProps} layout="floating" />);
    expect(screen.getByTitle('Dock to side')).toBeInTheDocument();
  });

  it('shows float button when layout is docked', () => {
    render(<ChatTitleBar {...defaultProps} layout="docked" />);
    expect(screen.getByTitle('Float')).toBeInTheDocument();
  });

  it('minimize button always visible', () => {
    render(<ChatTitleBar {...defaultProps} />);
    expect(screen.getByTitle('Minimize')).toBeInTheDocument();
  });

  it('close button always visible', () => {
    render(<ChatTitleBar {...defaultProps} />);
    expect(screen.getByTitle('Close')).toBeInTheDocument();
  });

  it('clicking dock calls onDock', async () => {
    const onDock = vi.fn();
    const user = userEvent.setup();
    render(<ChatTitleBar {...defaultProps} layout="floating" onDock={onDock} />);
    await user.click(screen.getByTitle('Dock to side'));
    expect(onDock).toHaveBeenCalled();
  });

  it('clicking close calls onClose', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<ChatTitleBar {...defaultProps} onClose={onClose} />);
    await user.click(screen.getByTitle('Close'));
    expect(onClose).toHaveBeenCalled();
  });
});
