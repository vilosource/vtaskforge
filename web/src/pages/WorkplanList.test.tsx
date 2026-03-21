import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkplanList } from './WorkplanList';

const WORKPLANS_URL = '/v1/workplans/';

const mockWorkplans = [
  {
    id: 'wp-1',
    name: 'Alpha Project',
    description: 'First workplan',
    status: 'active',
    tags: ['frontend', 'urgent'],
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'wp-2',
    name: 'Beta Project',
    description: 'Second workplan',
    status: 'draft',
    tags: ['backend'],
    created_at: '2024-01-02T00:00:00Z',
  },
];

const server = setupServer(
  http.get(WORKPLANS_URL, () =>
    HttpResponse.json({
      count: 2,
      next: null,
      previous: null,
      results: mockWorkplans,
    }),
  ),
  http.get('/v1/workplans/:id/stats/', () =>
    HttpResponse.json({
      total_tasks: 10,
      by_status: { draft: 2, todo: 3, doing: 1, done: 4 },
      completed_percentage: 40,
    }),
  ),
  http.get('/v1/workplans/:id/milestones/', () =>
    HttpResponse.json({
      count: 3,
      next: null,
      previous: null,
      results: [
        { id: 'milestone-1', name: 'Setup', status: 'completed' },
        { id: 'milestone-2', name: 'Implementation', status: 'active' },
        { id: 'milestone-3', name: 'Testing', status: 'pending' },
      ],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderWorkplanList() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <WorkplanList />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('WorkplanList', () => {
  it('renders loading state initially', () => {
    renderWorkplanList();
    expect(screen.getByText('Loading workplans...')).toBeInTheDocument();
  });

  it('renders workplans in a table after loading', async () => {
    renderWorkplanList();

    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument();
    });

    expect(screen.getByText('Beta Project')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
    expect(screen.getByText('draft')).toBeInTheDocument();
    expect(screen.getByText('frontend, urgent')).toBeInTheDocument();
    expect(screen.getByText('backend')).toBeInTheDocument();

    expect(screen.getByRole('table')).toBeInTheDocument();
    const rows = screen.getAllByRole('row');
    // 1 header row + 2 data rows
    expect(rows).toHaveLength(3);
  });

  it('renders empty state when no workplans', async () => {
    server.use(
      http.get(WORKPLANS_URL, () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );

    renderWorkplanList();

    await waitFor(() => {
      expect(screen.getByText('No workplans yet.')).toBeInTheDocument();
    });
  });

  it('renders error state with retry button on fetch failure', async () => {
    server.use(
      http.get(WORKPLANS_URL, () => HttpResponse.json({ detail: 'Server error' }, { status: 500 })),
    );

    renderWorkplanList();

    await waitFor(() => {
      expect(screen.getByText(/Failed to load workplans/i)).toBeInTheDocument();
    });

    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('each workplan name is a link to /workplans/:id', async () => {
    renderWorkplanList();

    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument();
    });

    const alphaLink = screen.getByRole('link', { name: 'Alpha Project' });
    expect(alphaLink).toHaveAttribute('href', '/workplans/wp-1');

    const betaLink = screen.getByRole('link', { name: 'Beta Project' });
    expect(betaLink).toHaveAttribute('href', '/workplans/wp-2');
  });

  it('clicking a workplan link navigates to /workplans/:id', async () => {
    const user = userEvent.setup();
    let navigatedTo = '';

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={['/']}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <WorkplanList />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText('Alpha Project')).toBeInTheDocument();
    });

    const link = screen.getByRole('link', { name: 'Alpha Project' });
    navigatedTo = link.getAttribute('href') ?? '';
    await user.click(link);

    expect(navigatedTo).toBe('/workplans/wp-1');
  });
});
