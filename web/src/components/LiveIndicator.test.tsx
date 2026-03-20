import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LiveIndicator } from './LiveIndicator';

describe('LiveIndicator', () => {
  it('shows "Live" when status is connected', () => {
    render(<LiveIndicator status="connected" />);
    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('shows "Reconnecting..." when status is reconnecting', () => {
    render(<LiveIndicator status="reconnecting" />);
    expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
  });

  it('shows "Offline" when status is disconnected', () => {
    render(<LiveIndicator status="disconnected" />);
    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  it('has connected class when status is connected', () => {
    const { container } = render(<LiveIndicator status="connected" />);
    expect(container.firstChild).toHaveClass('live-indicator--connected');
  });

  it('has reconnecting class when status is reconnecting', () => {
    const { container } = render(<LiveIndicator status="reconnecting" />);
    expect(container.firstChild).toHaveClass('live-indicator--reconnecting');
  });

  it('has disconnected class when status is disconnected', () => {
    const { container } = render(<LiveIndicator status="disconnected" />);
    expect(container.firstChild).toHaveClass('live-indicator--disconnected');
  });
});
