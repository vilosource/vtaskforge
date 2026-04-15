import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { ChatWidget } from '../ChatWidget';
import { ChatWidgetProvider, useChatWidget } from '../../contexts/ChatWidgetContext';

// Mock bridge API
vi.mock('../../api/bridge', () => ({
  checkLock: vi.fn().mockResolvedValue([]),
  acquireLock: vi.fn().mockResolvedValue({ session_id: 'test-sess' }),
  releaseLock: vi.fn().mockResolvedValue(undefined),
}));

// Mock stream hook
vi.mock('../../hooks/useBridgeStream', () => ({
  useBridgeStream: vi.fn(() => ({
    startStream: vi.fn(),
    cancelStream: vi.fn(),
    isStreaming: false,
    events: [],
    error: null,
  })),
}));

function TestWrapper({ children }: { children: React.ReactNode }) {
  return <ChatWidgetProvider>{children}</ChatWidgetProvider>;
}

function OpenAndRender({ project }: { project: string }) {
  const { open } = useChatWidget();
  return (
    <button onClick={() => open(project)} data-testid="open-btn">
      Open
    </button>
  );
}

describe('ChatWidget', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('vtf_token', 'test-token');
    vi.clearAllMocks();
  });

  it('renders when context is open', async () => {
    const user = userEvent.setup();
    render(
      <TestWrapper>
        <OpenAndRender project="test-proj" />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    expect(screen.getByTestId('chat-widget')).toBeInTheDocument();
  });

  it('hidden when context is closed', () => {
    const { container } = render(
      <TestWrapper>
        <ChatWidget />
      </TestWrapper>,
    );
    expect(container.querySelector('[data-testid="chat-widget"]')).toBeNull();
  });

  it('title bar shows project name', async () => {
    const user = userEvent.setup();
    render(
      <TestWrapper>
        <OpenAndRender project="my-proj" />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    expect(screen.getByText(/my-proj/)).toBeInTheDocument();
  });

  it('dock changes layout', async () => {
    const user = userEvent.setup();

    function LayoutDisplay() {
      const { layout } = useChatWidget();
      return <span data-testid="layout">{layout}</span>;
    }

    render(
      <TestWrapper>
        <OpenAndRender project="proj" />
        <LayoutDisplay />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    expect(screen.getByTestId('layout').textContent).toBe('floating');

    await user.click(screen.getByTitle('Dock to side'));
    expect(screen.getByTestId('layout').textContent).toBe('docked');
  });

  it('minimize shows minimized bar', async () => {
    const user = userEvent.setup();

    function LayoutDisplay() {
      const { layout } = useChatWidget();
      return <span data-testid="layout">{layout}</span>;
    }

    render(
      <TestWrapper>
        <OpenAndRender project="proj" />
        <LayoutDisplay />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    await user.click(screen.getByTitle('Minimize'));
    expect(screen.getByTestId('layout').textContent).toBe('minimized');
    expect(screen.getByTestId('chat-minimized-bar')).toBeInTheDocument();
  });

  it('restore from minimized', async () => {
    const user = userEvent.setup();

    function LayoutDisplay() {
      const { layout } = useChatWidget();
      return <span data-testid="layout">{layout}</span>;
    }

    render(
      <TestWrapper>
        <OpenAndRender project="proj" />
        <LayoutDisplay />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    await user.click(screen.getByTitle('Minimize'));
    expect(screen.getByTestId('layout').textContent).toBe('minimized');

    // Click minimized bar to restore
    await user.click(screen.getByTestId('chat-minimized-bar'));
    expect(screen.getByTestId('layout').textContent).toBe('floating');
  });

  it('close shows confirmation dialog when connected', async () => {
    const user = userEvent.setup();
    render(
      <TestWrapper>
        <OpenAndRender project="proj" />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    expect(screen.getByTestId('chat-widget')).toBeInTheDocument();

    await user.click(screen.getByTitle('Close'));
    // Should show close dialog, not immediately close
    expect(screen.getByTestId('close-release')).toBeInTheDocument();
    expect(screen.getByTestId('close-keep-alive')).toBeInTheDocument();
    expect(screen.getByTestId('close-cancel')).toBeInTheDocument();
  });

  it('release in close dialog removes widget', async () => {
    const user = userEvent.setup();
    render(
      <TestWrapper>
        <OpenAndRender project="proj" />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    await user.click(screen.getByTitle('Close'));
    await user.click(screen.getByTestId('close-release'));
    expect(screen.queryByTestId('chat-widget')).not.toBeInTheDocument();
  });

  it('keep alive in close dialog minimizes widget', async () => {
    const user = userEvent.setup();

    function LayoutDisplay() {
      const { layout } = useChatWidget();
      return <span data-testid="layout">{layout}</span>;
    }

    render(
      <TestWrapper>
        <OpenAndRender project="proj" />
        <LayoutDisplay />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    await user.click(screen.getByTitle('Close'));
    await user.click(screen.getByTestId('close-keep-alive'));
    expect(screen.getByTestId('layout').textContent).toBe('minimized');
  });

  it('has chat input area', async () => {
    const user = userEvent.setup();
    render(
      <TestWrapper>
        <OpenAndRender project="proj" />
        <ChatWidget />
      </TestWrapper>,
    );

    await user.click(screen.getByTestId('open-btn'));
    expect(screen.getByTestId('chat-input')).toBeInTheDocument();
  });
});
