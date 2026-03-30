import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }: any) => <a href={to} {...props}>{children}</a>,
  useParams: () => ({ id: 'proj-1' }),
  useNavigate: () => vi.fn(),
}));

const mockOpen = vi.fn();
vi.mock('../../contexts/ConsoleWidgetContext', () => ({
  useConsoleWidget: () => ({ open: mockOpen }),
}));

vi.mock('../../contexts/ActiveProjectContext', () => ({
  useSetActiveProject: () => {},
}));

vi.mock('../../api/projects', () => ({
  useProject: () => ({
    data: { id: 'proj-1', name: 'Test Project', description: 'desc', tags: [] },
    isLoading: false,
  }),
  useProjectStats: () => ({
    data: { total_tasks: 10, by_status: { done: 5, doing: 2, todo: 3 }, completed_percentage: 50, backlog_tasks: 0 },
  }),
  useProjectWorkplans: () => ({ data: [], isLoading: false }),
}));

vi.mock('../../api/tasks', () => ({
  useBacklogTasks: () => ({ data: { results: [] } }),
}));

vi.mock('../../hooks/useSSE', () => ({
  useSSE: () => ({ status: 'closed' }),
}));

vi.mock('../../api/console', () => ({
  openConsoleNewTab: vi.fn(),
}));

vi.mock('../../components/LiveIndicator', () => ({
  LiveIndicator: () => <div>live</div>,
}));

vi.mock('../../components/Breadcrumb', () => ({
  Breadcrumb: () => <nav>breadcrumb</nav>,
}));

vi.mock('../../components/TaskListTable', () => ({
  TaskListTable: () => <div>table</div>,
  BACKLOG_COLUMNS: [],
}));

describe('ProjectDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('"Plan with Architect" button opens widget with project', async () => {
    const { ProjectDashboard } = await import('../ProjectDashboard');
    const user = userEvent.setup();

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <ProjectDashboard />
      </QueryClientProvider>,
    );

    const btn = screen.getByText('Plan with Architect');
    expect(btn).toBeInTheDocument();

    await user.click(btn);
    expect(mockOpen).toHaveBeenCalledWith({ role: 'architect', project: 'proj-1' });
  });
});
