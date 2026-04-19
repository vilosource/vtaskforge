import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';

// Mock bridge API
vi.mock('../../api/bridge', () => ({
  checkLock: vi.fn().mockResolvedValue([]),
  acquireLock: vi.fn().mockResolvedValue({ session_id: 'sess-1' }),
  releaseLock: vi.fn().mockResolvedValue(undefined),
  fetchSessionHistory: vi.fn().mockResolvedValue({ turns: [], truncated: false }),
}));

vi.mock('../../hooks/useBridgeStream', () => ({
  useBridgeStream: vi.fn(() => ({
    startStream: vi.fn(),
    cancelStream: vi.fn(),
    isStreaming: false,
    events: [],
    error: null,
  })),
}));

// Mock API calls used by Home
vi.mock('../../api/projects', () => ({
  useProjects: vi.fn(() => ({
    data: { results: [{ id: 'p1', name: 'test-project', slug: 'test-project' }] },
    isLoading: false,
  })),
}));

vi.mock('../../api/agents', () => ({
  useAgents: vi.fn(() => ({
    data: { results: [] },
    isLoading: false,
  })),
}));

vi.mock('../../api/profile', () => ({
  useRecentAccess: vi.fn(() => ({ data: { results: [] }, isLoading: false })),
}));

vi.mock('../../api/client', () => ({
  apiGet: vi.fn().mockResolvedValue({ total_tasks: 0, by_status: {} }),
  apiGetPaginated: vi.fn().mockResolvedValue([]),
}));

// Must import after mocks
import { Home } from '../Home';
import { ChatWidgetProvider, useChatWidget } from '../../contexts/ChatWidgetContext';
import { ConsoleWidgetProvider } from '../../contexts/ConsoleWidgetContext';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function TestWrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ConsoleWidgetProvider>
          <ChatWidgetProvider>
            {children}
          </ChatWidgetProvider>
        </ConsoleWidgetProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('Home — Chat with Architect button', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('renders Chat with Architect button', async () => {
    render(
      <TestWrapper>
        <Home />
      </TestWrapper>,
    );

    const btn = await screen.findByText('Chat with Architect');
    expect(btn).toBeInTheDocument();
  });

  it('clicking Chat with Architect opens chat widget', async () => {
    function ChatStateDisplay() {
      const { isOpen } = useChatWidget();
      return <span data-testid="chat-open">{String(isOpen)}</span>;
    }

    const user = userEvent.setup();
    render(
      <TestWrapper>
        <ChatStateDisplay />
        <Home />
      </TestWrapper>,
    );

    expect(screen.getByTestId('chat-open').textContent).toBe('false');

    const btn = await screen.findByText('Chat with Architect');
    await user.click(btn);

    expect(screen.getByTestId('chat-open').textContent).toBe('true');
  });
});
