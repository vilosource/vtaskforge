import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ActiveProjectProvider, useSetActiveProject } from '../contexts/ActiveProjectContext';
import { Sidebar } from './Sidebar';

const mockProjects = [
  {
    id: 'proj-1',
    name: 'Alpha',
    status: 'active',
    description: '',
    repo_url: null,
    default_branch: 'main',
    tags: [],
    owner: null,
    created_by: 'admin',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'proj-2',
    name: 'Beta',
    status: 'draft',
    description: '',
    repo_url: null,
    default_branch: 'main',
    tags: [],
    owner: null,
    created_by: 'admin',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
];

const server = setupServer(
  http.get('/v1/projects/', () =>
    HttpResponse.json({ count: 2, next: null, previous: null, results: mockProjects }),
  ),
  http.get('/v1/projects/:id/stats/', () =>
    HttpResponse.json({
      project_id: 'proj-1',
      total_tasks: 0,
      backlog_tasks: 0,
      workplan_tasks: 0,
      by_status: {},
      completed_percentage: 0,
      workplans: { active: 0, completed: 0, archived: 0 },
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

describe('Sidebar', () => {
  it('renders the brand link', () => {
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter>
          <ActiveProjectProvider>
            <Sidebar />
          </ActiveProjectProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText('VTaskForge')).toBeInTheDocument();
  });

  it('renders project list after loading', async () => {
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter>
          <ActiveProjectProvider>
            <Sidebar />
          </ActiveProjectProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText('Alpha')).toBeInTheDocument();
    });
    expect(screen.getByText('Beta')).toBeInTheDocument();
  });

  it('marks the project active based on ActiveProjectContext, not useParams', async () => {
    // A helper that sets active project via context (simulates what a page would do).
    function PageSimulator({ activeId }: { activeId: string }) {
      useSetActiveProject(activeId);
      return <Sidebar />;
    }

    // Place us on a tasks/:id URL — if Sidebar read useParams it would get
    // a task-id, not a project-id, and no sidebar item would be highlighted.
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={['/tasks/some-task-id']}>
          <ActiveProjectProvider>
            <PageSimulator activeId="proj-1" />
          </ActiveProjectProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText('Alpha')).toBeInTheDocument();
    });

    // proj-1 (Alpha) should be active; proj-2 (Beta) should not
    const alphaLink = screen.getByRole('link', { name: /Alpha/ });
    expect(alphaLink).toHaveClass('sidebar-wp-item--active');

    const betaLink = screen.getByRole('link', { name: /Beta/ });
    expect(betaLink).not.toHaveClass('sidebar-wp-item--active');
  });
});
