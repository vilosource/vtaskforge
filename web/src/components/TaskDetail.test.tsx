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
};

const server = setupServer(
  http.get(TASK_URL, () => HttpResponse.json(baseTaskDetail)),
  http.post('/v1/tasks/task-1/:action/', () => HttpResponse.json({})),
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
});
