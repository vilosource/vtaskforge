import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConsoleWidget } from '../ConsoleWidget';
import { ConsoleWidgetProvider, useConsoleWidget } from '../../contexts/ConsoleWidgetContext';
import { act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';

// Mock the console API
vi.mock('../../api/console', () => ({
  buildAuthenticatedConsoleUrl: vi.fn().mockResolvedValue(
    'https://console.dev.viloforge.com/?role=architect&embed=true&code=test123',
  ),
}));

function TestWrapper({ children }: { children: React.ReactNode }) {
  return <ConsoleWidgetProvider>{children}</ConsoleWidgetProvider>;
}

// Helper to open the widget from a test
function OpenAndRender({ role, project }: { role?: string; project?: string }) {
  const { open } = useConsoleWidget();
  return (
    <button onClick={() => open({ role, project })} data-testid="open-btn">
      Open
    </button>
  );
}

describe('ConsoleWidget (WidgetContainer)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('renders when context is open', async () => {
    render(
      <TestWrapper>
        <OpenAndRender role="architect" project="test-proj" />
        <ConsoleWidget />
      </TestWrapper>,
    );

    // Click open button
    await act(async () => {
      screen.getByTestId('open-btn').click();
    });

    expect(screen.getByText(/architect/i)).toBeInTheDocument();
  });

  it('hidden when context is closed', () => {
    const { container } = render(
      <TestWrapper>
        <ConsoleWidget />
      </TestWrapper>,
    );

    // Widget should not render anything
    expect(container.querySelector('[data-testid="console-widget"]')).toBeNull();
  });

  it('title bar shows role and project', async () => {
    render(
      <TestWrapper>
        <OpenAndRender role="architect" project="my-proj" />
        <ConsoleWidget />
      </TestWrapper>,
    );

    await act(async () => {
      screen.getByTestId('open-btn').click();
    });

    expect(screen.getByText(/architect/i)).toBeInTheDocument();
    expect(screen.getByText(/my-proj/i)).toBeInTheDocument();
  });
});
