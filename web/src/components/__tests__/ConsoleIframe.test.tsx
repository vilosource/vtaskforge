import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ConsoleIframe } from '../ConsoleIframe';

// Mock the console API
vi.mock('../../api/console', () => ({
  buildAuthenticatedConsoleUrl: vi.fn().mockResolvedValue(
    'https://console.dev.viloforge.com/?role=architect&embed=true&code=test123',
  ),
}));

describe('ConsoleIframe', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders iframe with embed=true param', async () => {
    const { container } = render(
      <ConsoleIframe target={{ role: 'architect' }} onStatusChange={() => {}} />,
    );
    await waitFor(() => {
      const iframe = container.querySelector('iframe');
      expect(iframe).toBeTruthy();
      expect(iframe!.src).toContain('embed=true');
    });
  });

  it('shows loading until connected message', async () => {
    render(
      <ConsoleIframe target={{ role: 'architect' }} onStatusChange={() => {}} />,
    );
    expect(screen.getByText('Loading console...')).toBeInTheDocument();
  });

  it('handles connected postMessage', async () => {
    const onStatusChange = vi.fn();
    render(
      <ConsoleIframe target={{ role: 'architect' }} onStatusChange={onStatusChange} />,
    );

    // Simulate postMessage from console iframe
    window.dispatchEvent(
      new MessageEvent('message', {
        data: { type: 'connected' },
        origin: 'https://console.dev.viloforge.com',
      }),
    );

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledWith('connected');
    });
  });

  it('handles error postMessage', async () => {
    const onStatusChange = vi.fn();
    render(
      <ConsoleIframe target={{ role: 'architect' }} onStatusChange={onStatusChange} />,
    );

    window.dispatchEvent(
      new MessageEvent('message', {
        data: { type: 'error', message: 'Connection refused' },
        origin: 'https://console.dev.viloforge.com',
      }),
    );

    await waitFor(() => {
      expect(onStatusChange).toHaveBeenCalledWith('error');
    });
  });
});
