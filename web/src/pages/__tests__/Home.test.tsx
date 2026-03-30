import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }: any) => <a href={to} {...props}>{children}</a>,
  useLocation: () => ({ pathname: '/' }),
}));

// Capture the open call from useConsoleWidget
const mockOpen = vi.fn();
vi.mock('../../contexts/ConsoleWidgetContext', () => ({
  useConsoleWidget: () => ({ open: mockOpen }),
}));

// Mock App auth
vi.mock('../../App', () => ({
  useAuth: () => ({ authenticated: true, loading: false, username: 'testuser' }),
}));

// Mock API hooks
vi.mock('../../api/projects', () => ({
  useProjects: () => ({ data: { results: [] }, isLoading: false }),
  useProjectStats: () => ({ data: null }),
  useProjectWorkplans: () => ({ data: [], isLoading: false }),
}));

vi.mock('../../api/agents', () => ({
  useAgents: () => ({ data: { results: [] }, isLoading: false }),
}));

vi.mock('../../api/client', () => ({
  apiGet: vi.fn(),
  apiGetPaginated: vi.fn(),
}));

vi.mock('../../api/console', () => ({
  openConsoleNewTab: vi.fn(),
}));

describe('Home', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('"Consult Architect" button exists and opens widget', async () => {
    // Dynamic import after mocks are set up
    const { Home } = await import('../Home');
    const user = userEvent.setup();

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <Home />
      </QueryClientProvider>,
    );

    const btn = screen.getByText('Consult Architect');
    expect(btn).toBeInTheDocument();

    await user.click(btn);
    expect(mockOpen).toHaveBeenCalledWith({ role: 'architect' });
  });
});
