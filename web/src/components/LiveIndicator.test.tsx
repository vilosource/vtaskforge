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

  it('has green background when status is connected', () => {
    const { container } = render(<LiveIndicator status="connected" />);
    expect(container.firstChild).toHaveClass('bg-green-100');
  });

  it('has yellow background when status is reconnecting', () => {
    const { container } = render(<LiveIndicator status="reconnecting" />);
    expect(container.firstChild).toHaveClass('bg-yellow-100');
  });

  it('has gray background when status is disconnected', () => {
    const { container } = render(<LiveIndicator status="disconnected" />);
    expect(container.firstChild).toHaveClass('bg-gray-100');
  });
});
