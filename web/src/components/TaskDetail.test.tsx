import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskDetail } from './TaskDetail';
import type { TaskDetail as TaskDetailType } from '../api/tasks';

const TASK_URL = '/v1/tasks/task-1/';

const baseTaskDetail: TaskDetailType = {
  id: 'task-1',
  title: 'Implement login form',
  status: 'draft',
  milestone: 'milestone-1',
  workplan: 'wp-1',
  project: 'project-1',
  labels: [],
  claimed_by: null,
  claimed_at: null,
  assigned_to: null,
  requires: [],
  description: 'Build the login form with email and password fields.',
  acceptance_criteria: ['Email field is present', 'Password field is present', 'Submit button works'],
  notes: [],
  spec: '',
  agent_model: '',
  test_command: {},
  judge: false,
  isolation: 'sequential',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  links: [
    {
      id: 'link-1',
      source_type: 'task',
      source_id: 'task-1',
      source_title: 'Implement login form',
      target_type: 'task',
      target_id: 'task-0',
      target_title: 'Setup project',
      link_type: 'depends_on',
      metadata: {},
      created_at: '2024-01-01T00:00:00Z',
    },
  ],
  reviews: [],
  events: [],
  traces: null,
};

const PROJECT_URL = '/v1/projects/project-1/';
const WORKPLAN_URL = '/v1/workplans/wp-1';
const MILESTONE_URL = '/v1/milestones/milestone-1/';

const mockProject = { id: 'project-1', name: 'My Project', description: '', status: 'active', repo_url: null, default_branch: 'main', tags: [], owner: null, created_by: 'admin', created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' };
const mockWorkplan = { id: 'wp-1', name: 'Sprint 1', description: '', status: 'active', tags: [], created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z', project: 'project-1' };
const mockMilestone = { id: 'milestone-1', name: 'M1: Setup', description: '', workplan: 'wp-1', status: 'active', order: 1, created_at: '2024-01-01T00:00:00Z' };

const server = setupServer(
  http.get(TASK_URL, () => HttpResponse.json(baseTaskDetail)),
  http.post('/v1/tasks/task-1/:action/', () => HttpResponse.json({})),
  http.get(PROJECT_URL, () => HttpResponse.json(mockProject)),
  http.get(WORKPLAN_URL, () => HttpResponse.json(mockWorkplan)),
  http.get(MILESTONE_URL, () => HttpResponse.json(mockMilestone)),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderModal(taskId: string | null = 'task-1', onClose = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    onClose,
    ...render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <TaskDetail taskId={taskId} onClose={onClose} />
        </QueryClientProvider>
      </MemoryRouter>,
    ),
  };
}

describe('TaskDetail modal (slim)', () => {
  it('renders nothing when taskId is null', () => {
    const { container } = renderModal(null);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders task title after loading', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
  });

  it('renders truncated description', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Build the login form with email and password fields.')).toBeInTheDocument();
    });
  });

  it('renders acceptance criteria', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Email field is present')).toBeInTheDocument();
    });
  });

  it('shows dependency with title', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Setup project')).toBeInTheDocument();
    });
  });

  it('shows "Open full view" link', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText(/Open full view/)).toBeInTheDocument();
    });
    const link = screen.getByText(/Open full view/).closest('a');
    expect(link).toHaveAttribute('href', '/tasks/task-1');
  });

  it('does not show event timeline or notes (moved to full page)', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.queryByText('Event Timeline')).not.toBeInTheDocument();
    expect(screen.queryByText('Notes')).not.toBeInTheDocument();
  });

  it('shows Submit button for draft status', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
    });
  });

  it('Escape key closes the modal', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal('task-1', onClose);
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('close button calls onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal('task-1', onClose);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /close/i })).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('renders error state when fetch fails', async () => {
    server.use(
      http.get(TASK_URL, () => HttpResponse.json({ detail: 'Not found' }, { status: 404 })),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('shows project name in hierarchy context line', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('My Project')).toBeInTheDocument();
    });
  });

  it('shows workplan name in hierarchy context line', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Sprint 1')).toBeInTheDocument();
    });
  });

  it('shows milestone name in hierarchy context line', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('M1: Setup')).toBeInTheDocument();
    });
  });

  it('project link navigates to correct route and calls onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal('task-1', onClose);
    await waitFor(() => {
      expect(screen.getByText('My Project')).toBeInTheDocument();
    });
    const link = screen.getByText('My Project').closest('a');
    expect(link).toHaveAttribute('href', '/projects/project-1');
    await user.click(screen.getByText('My Project'));
    expect(onClose).toHaveBeenCalled();
  });

  it('workplan link navigates to correct route', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Sprint 1')).toBeInTheDocument();
    });
    const link = screen.getByText('Sprint 1').closest('a');
    expect(link).toHaveAttribute('href', '/projects/project-1/workplans/wp-1');
  });

  it('milestone link navigates to correct route', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('M1: Setup')).toBeInTheDocument();
    });
    const link = screen.getByText('M1: Setup').closest('a');
    expect(link).toHaveAttribute('href', '/projects/project-1/workplans/wp-1/milestones/milestone-1');
  });

  it('handles missing milestone gracefully', async () => {
    const taskNoMilestone = { ...baseTaskDetail, milestone: '' };
    server.use(
      http.get(TASK_URL, () => HttpResponse.json(taskNoMilestone)),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    // should not throw, project still shown
    await waitFor(() => {
      expect(screen.getByText('My Project')).toBeInTheDocument();
    });
    expect(screen.queryByText('M1: Setup')).not.toBeInTheDocument();
  });

  it('context line is above the task title', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('My Project')).toBeInTheDocument();
    });
    // The context breadcrumb (project/workplan/milestone) should appear before the title in DOM order
    const projectEl = screen.getByText('My Project');
    const titleEl = screen.getByText('Implement login form');
    const result = projectEl.compareDocumentPosition(titleEl);
    // DOCUMENT_POSITION_FOLLOWING (4) means titleEl comes after projectEl
    expect(result & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
