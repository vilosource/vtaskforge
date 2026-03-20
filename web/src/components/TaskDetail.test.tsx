import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskDetail } from './TaskDetail';
import type { TaskDetail as TaskDetailType } from '../api/tasks';

const TASK_URL = '/v1/tasks/task-1/';

const baseTaskDetail: TaskDetailType = {
  id: 'task-1',
  title: 'Implement login form',
  status: 'draft',
  phase_id: 'phase-1',
  workplan_id: 'wp-1',
  claimed_by: null,
  claimed_at: null,
  assigned_to: null,
  requires: [],
  description: 'Build the login form with email and password fields.',
  acceptance_criteria: ['Email field is present', 'Password field is present', 'Submit button works'],
  notes: [],
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  links: [
    {
      id: 'link-1',
      source_id: 'task-1',
      target_id: 'auth-area',
      link_type: 'area',
      metadata: {},
      created_at: '2024-01-01T00:00:00Z',
    },
  ],
  reviews: [
    {
      id: 'review-1',
      decision: 'approved',
      reason: null,
      reviewer_id: 'human-jason',
      reviewer_type: 'human',
      created_at: '2024-01-02T00:00:00Z',
    },
  ],
  events: [
    {
      id: 'evt-1',
      event_type: 'status_changed',
      data: { from: 'draft', to: 'todo' },
      created_at: '2024-01-01T10:00:00Z',
    },
    {
      id: 'evt-2',
      event_type: 'claimed',
      data: { agent_id: 'agent-7' },
      created_at: '2024-01-01T11:00:00Z',
    },
  ],
};

const server = setupServer(
  http.get(TASK_URL, ({ request }) => {
    const url = new URL(request.url);
    if (url.searchParams.get('expand') === 'links,reviews,events') {
      return HttpResponse.json(baseTaskDetail);
    }
    return HttpResponse.json(baseTaskDetail);
  }),
  // Catch-all for mutation endpoints to avoid unhandled request errors in most tests
  http.post('/v1/tasks/task-1/:action/', () => HttpResponse.json({})),
  http.post('/v1/tasks/task-1/notes/', () => HttpResponse.json({ id: 'note-1', text: 'hello', actor_id: 'human', created_at: '2024-01-01T00:00:00Z' })),
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
      <QueryClientProvider client={queryClient}>
        <TaskDetail taskId={taskId} onClose={onClose} />
      </QueryClientProvider>,
    ),
  };
}

describe('TaskDetail', () => {
  it('renders nothing when taskId is null', () => {
    const { container } = renderModal(null);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders loading state initially', () => {
    renderModal();
    expect(screen.getAllByText(/loading/i).length).toBeGreaterThan(0);
  });

  it('renders task title and description after loading', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByText('Build the login form with email and password fields.')).toBeInTheDocument();
  });

  it('renders acceptance criteria as a list', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Email field is present')).toBeInTheDocument();
    });
    expect(screen.getByText('Password field is present')).toBeInTheDocument();
    expect(screen.getByText('Submit button works')).toBeInTheDocument();
  });

  it('renders event timeline with events', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    // Events section should exist
    expect(screen.getByText('Event Timeline')).toBeInTheDocument();
    // status_changed event shows from/to (may appear multiple times due to status badge)
    expect(screen.getAllByText('draft').length).toBeGreaterThan(0);
    expect(screen.getAllByText('todo').length).toBeGreaterThan(0);
  });

  it('shows Submit button for draft status', async () => {
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
  });

  it('shows Claim button for todo status', async () => {
    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'todo' }),
      ),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /claim/i })).toBeInTheDocument();
  });

  it('shows Complete, Fail, Block buttons for doing status', async () => {
    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'doing' }),
      ),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /complete/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fail/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /block/i })).toBeInTheDocument();
  });

  it('shows Approve, Reject, Request Changes for pending_start_review', async () => {
    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'pending_start_review' }),
      ),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request changes/i })).toBeInTheDocument();
  });

  it('shows Unblock button for blocked status', async () => {
    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'blocked' }),
      ),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /unblock/i })).toBeInTheDocument();
  });

  it('shows Rewrite, Back to pool, Cancel for needs_attention', async () => {
    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'needs_attention' }),
      ),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /rewrite/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /back to pool/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });

  it('shows no action buttons for done status (terminal)', async () => {
    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'done' }),
      ),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.queryByRole('button', { name: /submit|claim|complete|fail|block|unblock|defer|cancel/i })).not.toBeInTheDocument();
  });

  it('Submit button calls POST /v1/tasks/:id/submit/', async () => {
    const user = userEvent.setup();
    let submitCalled = false;

    server.use(
      http.post('/v1/tasks/task-1/submit/', () => {
        submitCalled = true;
        return HttpResponse.json({});
      }),
    );

    renderModal();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^submit$/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /^submit$/i }));
    await waitFor(() => {
      expect(submitCalled).toBe(true);
    });
  });

  it('Claim button shows agent input and calls POST /v1/tasks/:id/claim/', async () => {
    const user = userEvent.setup();
    let claimBody: Record<string, unknown> = {};

    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'todo' }),
      ),
      http.post('/v1/tasks/task-1/claim/', async ({ request }) => {
        claimBody = await request.json() as Record<string, unknown>;
        return HttpResponse.json({});
      }),
    );

    renderModal();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^claim$/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /^claim$/i }));

    // Agent input should appear
    const agentInput = screen.getByLabelText(/agent id/i);
    expect(agentInput).toBeInTheDocument();

    await user.type(agentInput, 'agent-claude');

    const confirmBtn = screen.getByRole('button', { name: /confirm claim/i });
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(claimBody).toMatchObject({ agent_id: 'agent-claude' });
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

  it('clicking backdrop closes the modal', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal('task-1', onClose);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    const overlay = screen.getByRole('dialog');
    // Click on the overlay itself (not the modal content)
    await user.click(overlay);
    expect(onClose).toHaveBeenCalled();
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

  it('add note form submits POST /v1/tasks/:id/notes/', async () => {
    const user = userEvent.setup();
    let notesBody: Record<string, unknown> = {};

    server.use(
      http.post('/v1/tasks/task-1/notes/', async ({ request }) => {
        notesBody = await request.json() as Record<string, unknown>;
        return HttpResponse.json({ id: 'note-2', text: 'test note', actor_id: 'human', created_at: '2024-01-02T00:00:00Z' });
      }),
    );

    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });

    const noteInput = screen.getByLabelText(/note text/i);
    await user.type(noteInput, 'test note');

    const addBtn = screen.getByRole('button', { name: /add note/i });
    await user.click(addBtn);

    await waitFor(() => {
      expect(notesBody).toMatchObject({ text: 'test note' });
    });
  });

  it('renders error state when fetch fails', async () => {
    server.use(
      http.get(TASK_URL, () => HttpResponse.json({ detail: 'Not found' }, { status: 404 })),
    );

    renderModal();
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
  });

  it('shows Defer and Cancel for non-terminal statuses', async () => {
    server.use(
      http.get(TASK_URL, () =>
        HttpResponse.json({ ...baseTaskDetail, status: 'draft' }),
      ),
    );
    renderModal();
    await waitFor(() => {
      expect(screen.getByText('Implement login form')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /defer/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
  });
});
