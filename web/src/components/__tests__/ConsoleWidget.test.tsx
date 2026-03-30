import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { ConsoleWidget } from '../ConsoleWidget';
import { ConsoleWidgetProvider, useConsoleWidget } from '../../contexts/ConsoleWidgetContext';
import { act } from '@testing-library/react';

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

  it('dock changes layout to docked', async () => {
    const user = userEvent.setup();

    function DockControl() {
      const { open, dock, layout } = useConsoleWidget();
      return (
        <>
          <button onClick={() => open({ role: 'architect' })} data-testid="open">Open</button>
          <button onClick={dock} data-testid="dock">Dock</button>
          <span data-testid="layout">{layout}</span>
        </>
      );
    }

    render(
      <TestWrapper>
        <DockControl />
        <ConsoleWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open'));
    await user.click(screen.getByTestId('dock'));
    expect(screen.getByTestId('layout').textContent).toBe('docked');
  });

  it('undock returns to floating', async () => {
    const user = userEvent.setup();

    function UndockControl() {
      const { open, dock, float, layout } = useConsoleWidget();
      return (
        <>
          <button onClick={() => open({ role: 'architect' })} data-testid="open">Open</button>
          <button onClick={dock} data-testid="dock">Dock</button>
          <button onClick={float} data-testid="float">Float</button>
          <span data-testid="layout">{layout}</span>
        </>
      );
    }

    render(
      <TestWrapper>
        <UndockControl />
        <ConsoleWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open'));
    await user.click(screen.getByTestId('dock'));
    expect(screen.getByTestId('layout').textContent).toBe('docked');
    await user.click(screen.getByTestId('float'));
    expect(screen.getByTestId('layout').textContent).toBe('floating');
  });

  it('minimize shows minimized bar', async () => {
    const user = userEvent.setup();

    function MinimizeControl() {
      const { open, minimize, layout } = useConsoleWidget();
      return (
        <>
          <button onClick={() => open({ role: 'architect', project: 'test-proj' })} data-testid="open">Open</button>
          <button onClick={minimize} data-testid="minimize">Minimize</button>
          <span data-testid="layout">{layout}</span>
        </>
      );
    }

    render(
      <TestWrapper>
        <MinimizeControl />
        <ConsoleWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open'));
    await user.click(screen.getByTestId('minimize'));
    expect(screen.getByTestId('layout').textContent).toBe('minimized');
    // MinimizedBar should be visible
    expect(screen.getByTestId('minimized-bar')).toBeInTheDocument();
  });

  it('restore from minimized', async () => {
    const user = userEvent.setup();

    function RestoreControl() {
      const { open, minimize, restore, layout } = useConsoleWidget();
      return (
        <>
          <button onClick={() => open({ role: 'architect' })} data-testid="open">Open</button>
          <button onClick={minimize} data-testid="minimize">Minimize</button>
          <button onClick={restore} data-testid="restore">Restore</button>
          <span data-testid="layout">{layout}</span>
        </>
      );
    }

    render(
      <TestWrapper>
        <RestoreControl />
        <ConsoleWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open'));
    await user.click(screen.getByTestId('minimize'));
    expect(screen.getByTestId('layout').textContent).toBe('minimized');
    await user.click(screen.getByTestId('restore'));
    expect(screen.getByTestId('layout').textContent).toBe('floating');
  });

  it('popout calls window.open and closes widget', async () => {
    const user = userEvent.setup();
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

    function PopoutControl() {
      const { open, isOpen } = useConsoleWidget();
      return (
        <>
          <button onClick={() => open({ role: 'architect' })} data-testid="open">Open</button>
          <span data-testid="is-open">{String(isOpen)}</span>
        </>
      );
    }

    render(
      <TestWrapper>
        <PopoutControl />
        <ConsoleWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open'));
    expect(screen.getByTestId('is-open').textContent).toBe('true');

    // Click the pop-out button in the widget title bar
    const popOutBtn = screen.getByTitle('Open in new tab');
    await user.click(popOutBtn);

    expect(windowOpenSpy).toHaveBeenCalled();
    expect(screen.getByTestId('is-open').textContent).toBe('false');

    windowOpenSpy.mockRestore();
  });
});
