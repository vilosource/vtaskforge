import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskPage } from './TaskPage';
import { ActiveProjectProvider } from '../contexts/ActiveProjectContext';

const mockTask = {
  id: 'task-abc',
  title: 'Fix the bug',
  status: 'todo',
  milestone: 'milestone-1',
  workplan: 'workplan-1',
  project: 'project-1',
  labels: [],
  claimed_by: null,
  claimed_at: null,
  assigned_to: null,
  requires: [],
  description: 'A task description',
  acceptance_criteria: ['AC1', 'AC2'],
  notes: [],
  spec: '',
  agent_model: 'sonnet',
  test_command: {},
  judge: false,
  isolation: 'sequential',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
  links: [],
  reviews: [],
  events: [],
};

const mockWorkplan = {
  id: 'workplan-1',
  name: 'Sprint One',
  description: '',
  status: 'active',
  tags: [],
  created_at: '2024-01-01T00:00:00Z',
};

const mockMilestone = {
  id: 'milestone-1',
  name: 'Milestone Alpha',
  workplan: 'workplan-1',
  status: 'active',
  order: 1,
  description: '',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockProject = {
  id: 'project-1',
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

const server = setupServer(
  http.get('/v1/tasks/task-abc/', () => HttpResponse.json(mockTask)),
  http.get('/v1/workplans/workplan-1', () => HttpResponse.json(mockWorkplan)),
  http.get('/v1/milestones/milestone-1/', () => HttpResponse.json(mockMilestone)),
  http.get('/v1/projects/project-1/', () => HttpResponse.json(mockProject)),
  http.get('/v1/links/', () => HttpResponse.json({ count: 0, results: [] })),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderTaskPage(taskId = 'task-abc') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ActiveProjectProvider>
        <MemoryRouter initialEntries={[`/tasks/${taskId}`]}>
          <Routes>
            <Route path="/tasks/:id" element={<TaskPage />} />
          </Routes>
        </MemoryRouter>
      </ActiveProjectProvider>
    </QueryClientProvider>
  );
}

describe('TaskPage', () => {
  it('renders task title after loading', async () => {
    renderTaskPage();
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Fix the bug' })).toBeInTheDocument());
  });

  it('breadcrumb uses /projects/:pid/workplans/:wid pattern for workplan link', async () => {
    renderTaskPage();
    await waitFor(() => screen.getByRole('heading', { name: 'Fix the bug' }));
    // Both breadcrumb and context card link to workplan — all should use project-scoped URL
    const workplanLinks = screen.getAllByRole('link', { name: 'Sprint One' });
    workplanLinks.forEach((link) => {
      expect(link.getAttribute('href')).toBe('/projects/project-1/workplans/workplan-1');
    });
  });

  it('breadcrumb uses /projects/:pid/workplans/:wid/milestones/:mid for milestone link', async () => {
    renderTaskPage();
    await waitFor(() => screen.getByRole('heading', { name: 'Fix the bug' }));
    const milestoneLinks = screen.getAllByRole('link', { name: 'Milestone Alpha' });
    const breadcrumbLink = milestoneLinks.find(
      (el) =>
        el.getAttribute('href') ===
        '/projects/project-1/workplans/workplan-1/milestones/milestone-1' &&
        el.closest('nav') !== null
    );
    expect(breadcrumbLink).toBeDefined();
    expect(breadcrumbLink!.getAttribute('href')).toBe(
      '/projects/project-1/workplans/workplan-1/milestones/milestone-1'
    );
  });

  it('breadcrumb shows project name as link to /projects/:pid', async () => {
    renderTaskPage();
    await waitFor(() => screen.getByRole('heading', { name: 'Fix the bug' }));
    const projectLink = screen.getByRole('link', { name: 'My Project' });
    expect(projectLink.getAttribute('href')).toBe('/projects/project-1');
  });

  it('context card workplan link uses /projects/:pid/workplans/:wid pattern', async () => {
    renderTaskPage();
    await waitFor(() => screen.getByRole('heading', { name: 'Fix the bug' }));
    // Context card renders workplan name as link — there are two (breadcrumb + context card)
    const workplanLinks = screen.getAllByRole('link', { name: 'Sprint One' });
    const contextLink = workplanLinks.find(
      (el) => el.getAttribute('href') === '/projects/project-1/workplans/workplan-1'
    );
    expect(contextLink).toBeDefined();
  });

  it('context card milestone link uses project-scoped pattern', async () => {
    renderTaskPage();
    await waitFor(() => screen.getByRole('heading', { name: 'Fix the bug' }));
    const milestoneLinks = screen.getAllByRole('link', { name: 'Milestone Alpha' });
    const contextLink = milestoneLinks.find(
      (el) =>
        el.getAttribute('href') ===
        '/projects/project-1/workplans/workplan-1/milestones/milestone-1'
    );
    expect(contextLink).toBeDefined();
  });

  it('no link in the page points to /workplans/ without project prefix', async () => {
    renderTaskPage();
    await waitFor(() => screen.getByRole('heading', { name: 'Fix the bug' }));
    const allLinks = screen.getAllByRole('link');
    const badLinks = allLinks.filter((el) => {
      const href = el.getAttribute('href') ?? '';
      return /^\/workplans\//.test(href);
    });
    expect(badLinks).toHaveLength(0);
  });
});
