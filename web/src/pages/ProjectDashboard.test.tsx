import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectDashboard } from './ProjectDashboard';
import { ActiveProjectProvider } from '../contexts/ActiveProjectContext';

const mockProject = {
  id: 'proj-1',
  name: 'My Awesome Project',
  description: 'A project description',
  status: 'active',
  repo_url: null,
  default_branch: 'main',
  tags: [],
  owner: null,
  created_by: 'admin',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockStats = {
  project_id: 'proj-1',
  total_tasks: 5,
  backlog_tasks: 1,
  workplan_tasks: 4,
  by_status: { todo: 2, doing: 1, done: 2 },
  completed_percentage: 40,
  workplans: { active: 1, completed: 0, archived: 0 },
};

const mockWorkplans = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 'wp-1',
      name: 'Sprint One',
      description: '',
      status: 'active',
      tags: [],
      created_at: '2024-01-01T00:00:00Z',
      total_tasks: 4,
      completed_percentage: 40,
    },
  ],
};

const mockBacklogTasks = {
  count: 0,
  next: null,
  previous: null,
  results: [],
};

const server = setupServer(
  http.get('/v1/projects/proj-1/', () => HttpResponse.json(mockProject)),
  http.get('/v1/projects/proj-1/stats/', () => HttpResponse.json(mockStats)),
  http.get('/v1/projects/proj-1/workplans/', () => HttpResponse.json(mockWorkplans)),
  http.get('/v1/tasks/', () => HttpResponse.json(mockBacklogTasks)),
  http.get('/v1/events/stream/', () => new HttpResponse(null, { status: 200 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderProjectDashboard(projectId = 'proj-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ActiveProjectProvider>
        <MemoryRouter initialEntries={[`/projects/${projectId}`]}>
          <Routes>
            <Route path="/projects/:id" element={<ProjectDashboard />} />
          </Routes>
        </MemoryRouter>
      </ActiveProjectProvider>
    </QueryClientProvider>,
  );
}

describe('ProjectDashboard', () => {
  it('renders breadcrumb with Projects link and project name after loading', async () => {
    renderProjectDashboard();
    await waitFor(() => screen.getByRole('heading', { name: 'My Awesome Project' }));

    const nav = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(nav).toBeInTheDocument();

    const projectsLink = screen.getByRole('link', { name: 'Projects' });
    expect(projectsLink).toBeInTheDocument();
    expect(projectsLink.getAttribute('href')).toBe('/');

    // Current breadcrumb segment is a bold span (not a link)
    const breadcrumbCurrent = screen.getAllByText('My Awesome Project').find(el => el.tagName === 'SPAN' && el.classList.contains('font-bold'));
    expect(breadcrumbCurrent).toBeInTheDocument();
  });

  it('breadcrumb Projects segment links to /', async () => {
    renderProjectDashboard();
    await waitFor(() => screen.getByRole('heading', { name: 'My Awesome Project' }));

    const projectsLink = screen.getByRole('link', { name: 'Projects' });
    expect(projectsLink.getAttribute('href')).toBe('/');
  });
});
