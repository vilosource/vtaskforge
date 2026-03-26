import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkplanDetail } from './WorkplanDetail';
import { ActiveProjectProvider } from '../contexts/ActiveProjectContext';

const mockWorkplan = {
  id: 'wp-1',
  name: 'Test Workplan',
  description: 'A test workplan',
  status: 'active',
  tags: [],
  created_at: '2024-01-01T00:00:00Z',
};

const mockProject = {
  id: 'proj-1',
  name: 'My Project',
  description: '',
  status: 'active',
  repo_url: null,
  default_branch: 'main',
  tags: [],
  owner: null,
  created_by: 'admin',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockWpStats = {
  total_tasks: 3,
  by_status: { todo: 2, done: 1 },
  completed_percentage: 33,
};

const mockMilestones = {
  count: 1,
  next: null,
  previous: null,
  results: [
    { id: 'ms-1', name: 'Phase 1', description: '', status: 'active' },
  ],
};

const mockOrphanTask = {
  id: 'task-orphan-1',
  title: 'Orphan Task Alpha',
  status: 'todo',
  milestone: null,
  workplan: 'wp-1',
  project: 'proj-1',
  labels: ['backend', 'urgent'],
  claimed_by: null,
  claimed_at: null,
  assigned_to: null,
  requires: [],
  description: 'An orphan task with no milestone',
  acceptance_criteria: [],
  notes: [],
  spec: '',
  agent_model: 'sonnet',
  test_command: {},
  judge: false,
  isolation: 'sequential',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
};

const mockTaskDetail = {
  ...mockOrphanTask,
  links: [],
  reviews: [],
  events: [],
  notes: [],
};

const server = setupServer(
  http.get('/v1/workplans/wp-1', () => HttpResponse.json(mockWorkplan)),
  http.get('/v1/workplans/wp-1/stats/', () => HttpResponse.json(mockWpStats)),
  http.get('/v1/projects/proj-1/', () => HttpResponse.json(mockProject)),
  http.get('/v1/workplans/wp-1/milestones/', () => HttpResponse.json(mockMilestones)),
  http.get('/v1/milestones/ms-1/stats/', () =>
    HttpResponse.json({ total_tasks: 0, by_status: {}, completed_percentage: 0 }),
  ),
  http.get('/v1/tasks/', (req) => {
    const url = new URL(req.request.url);
    const milestoneNull = url.searchParams.get('milestone__isnull');
    if (milestoneNull === 'true') {
      return HttpResponse.json({
        count: 1,
        next: null,
        previous: null,
        results: [mockOrphanTask],
      });
    }
    return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
  }),
  http.get('/v1/tasks/task-orphan-1/', () => HttpResponse.json(mockTaskDetail)),
  http.get('/v1/links/', () => HttpResponse.json({ count: 0, results: [] })),
  http.get('/v1/events/stream/', () => new HttpResponse(null, { status: 200 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWorkplanDetail() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ActiveProjectProvider>
        <MemoryRouter initialEntries={['/projects/proj-1/workplans/wp-1']}>
          <Routes>
            <Route path="/projects/:id/workplans/:wid" element={<WorkplanDetail />} />
          </Routes>
        </MemoryRouter>
      </ActiveProjectProvider>
    </QueryClientProvider>,
  );
}

describe('WorkplanDetail — Unassigned Tasks', () => {
  it('shows Unassigned Tasks section when orphan tasks exist', async () => {
    renderWorkplanDetail();

    await waitFor(() => {
      expect(screen.getByText('Unassigned Tasks')).toBeInTheDocument();
    });

    expect(screen.getByText('Orphan Task Alpha')).toBeInTheDocument();
  });

  it('shows task status badge in unassigned tasks section', async () => {
    renderWorkplanDetail();

    await waitFor(() => {
      expect(screen.getByText('Orphan Task Alpha')).toBeInTheDocument();
    });

    // Should show status badge
    expect(screen.getByText('todo')).toBeInTheDocument();
  });

  it('shows task labels in unassigned tasks section', async () => {
    renderWorkplanDetail();

    await waitFor(() => {
      expect(screen.getByText('Orphan Task Alpha')).toBeInTheDocument();
    });

    expect(screen.getByText('backend')).toBeInTheDocument();
    expect(screen.getByText('urgent')).toBeInTheDocument();
  });

  it('clicking an orphan task opens the TaskDetail modal', async () => {
    const user = userEvent.setup();
    renderWorkplanDetail();

    await waitFor(() => {
      expect(screen.getByText('Orphan Task Alpha')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Orphan Task Alpha'));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  it('does not show Unassigned Tasks section when no orphan tasks exist', async () => {
    server.use(
      http.get('/v1/tasks/', () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );

    renderWorkplanDetail();

    // Wait for workplan title heading to load
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Test Workplan' })).toBeInTheDocument();
    });

    // Give time for orphan task query to settle
    await waitFor(() => {
      expect(screen.queryByText('Unassigned Tasks')).not.toBeInTheDocument();
    });
  });
});
