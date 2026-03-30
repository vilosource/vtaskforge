import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';

// Mock react-router-dom
vi.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }: any) => <a href={to} {...props}>{children}</a>,
  useParams: () => ({ id: 'task-1' }),
}));

const mockOpen = vi.fn();
vi.mock('../../contexts/ConsoleWidgetContext', () => ({
  useConsoleWidget: () => ({ open: mockOpen }),
}));

vi.mock('../../contexts/ActiveProjectContext', () => ({
  useSetActiveProject: () => {},
}));

vi.mock('../../api/tasks', () => ({
  useTaskDetail: vi.fn(),
  useDownstreamLinks: () => ({ data: { results: [] } }),
  useWorkplan: () => ({ data: null }),
}));

vi.mock('../../api/milestones', () => ({
  useMilestone: () => ({ data: null }),
}));

vi.mock('../../api/projects', () => ({
  useProject: () => ({ data: { name: 'proj' } }),
}));

vi.mock('../../utils/parseSpec', () => ({
  parseSpec: () => null,
}));

vi.mock('../../components/SpecSection', () => ({
  SpecSection: () => null,
}));

vi.mock('../../components/DependencyChain', () => ({
  DependencyChain: () => null,
}));

vi.mock('../../components/EventTimeline', () => ({
  EventTimeline: () => null,
}));

vi.mock('../../components/ActionButtons', () => ({
  ActionButtons: () => <div>actions</div>,
}));

vi.mock('../../components/AddNoteForm', () => ({
  AddNoteForm: () => null,
}));

vi.mock('../../components/Breadcrumb', () => ({
  Breadcrumb: () => <nav>breadcrumb</nav>,
}));

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    id: 'task-1',
    title: 'Test Task',
    status: 'doing',
    milestone: '',
    workplan: '',
    project: 'proj-1',
    labels: [],
    claimed_by: 'agent-1',
    claimed_by_pod_name: 'pod-abc-123',
    claimed_at: null,
    assigned_to: null,
    requires: [],
    description: 'desc',
    acceptance_criteria: [],
    notes: [],
    spec: '',
    agent_model: '',
    test_command: {},
    judge: false,
    isolation: '',
    created_at: '2025-01-01',
    updated_at: '2025-01-01',
    links: [],
    reviews: [],
    events: [],
    traces: null,
    ...overrides,
  };
}

describe('TaskPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Debug button visible when task doing with claimed_by_pod_name', async () => {
    const { useTaskDetail } = await import('../../api/tasks');
    (useTaskDetail as any).mockReturnValue({
      data: makeTask(),
      isLoading: false,
      isError: false,
    });

    const { TaskPage } = await import('../TaskPage');
    render(<TaskPage />);

    expect(screen.getByText('Debug')).toBeInTheDocument();
  });

  it('Debug button hidden when no pod_name', async () => {
    const { useTaskDetail } = await import('../../api/tasks');
    (useTaskDetail as any).mockReturnValue({
      data: makeTask({ claimed_by_pod_name: null }),
      isLoading: false,
      isError: false,
    });

    const { TaskPage } = await import('../TaskPage');
    render(<TaskPage />);

    expect(screen.queryByText('Debug')).not.toBeInTheDocument();
  });

  it('Debug opens widget with correct pod', async () => {
    const { useTaskDetail } = await import('../../api/tasks');
    (useTaskDetail as any).mockReturnValue({
      data: makeTask(),
      isLoading: false,
      isError: false,
    });

    const { TaskPage } = await import('../TaskPage');
    const user = userEvent.setup();

    render(<TaskPage />);

    await user.click(screen.getByText('Debug'));
    expect(mockOpen).toHaveBeenCalledWith({ pod: 'pod-abc-123', command: 'bash' });
  });
});
