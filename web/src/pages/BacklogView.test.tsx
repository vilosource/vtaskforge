import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BacklogView } from './BacklogView';
import { ActiveProjectProvider } from '../contexts/ActiveProjectContext';

const server = setupServer(
  http.get('/v1/projects/:projectId/', ({ params }) =>
    HttpResponse.json({
      id: params.projectId,
      name: 'Test Project',
      description: '',
      status: 'active',
      repo_url: null,
      default_branch: 'main',
      tags: [],
      owner: null,
      created_by: 'admin',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    }),
  ),
  http.get('/v1/tasks/', () =>
    HttpResponse.json({
      count: 0,
      next: null,
      previous: null,
      results: [],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderBacklogView(projectId = 'proj-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/projects/${projectId}/backlog`]}>
        <ActiveProjectProvider>
          <Routes>
            <Route path="/projects/:id/backlog" element={<BacklogView />} />
          </Routes>
        </ActiveProjectProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('BacklogView', () => {
  it('renders Breadcrumb component with correct segments', async () => {
    renderBacklogView('proj-1');

    // Wait for project data to load and breadcrumb to show project name
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Test Project' })).toBeInTheDocument();
    });

    const breadcrumbNav = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(breadcrumbNav).toBeInTheDocument();

    // Project link
    const projectLink = screen.getByRole('link', { name: 'Test Project' });
    expect(projectLink).toHaveAttribute('href', '/projects/proj-1');

    // Backlog current segment (no link)
    const backlogSpan = screen.getByText('Backlog');
    expect(backlogSpan.tagName).toBe('SPAN');
    expect(backlogSpan).toHaveClass('font-bold');
  });

  it('does not render inline breadcrumb styles (no inline flex display breadcrumb)', async () => {
    const { container } = renderBacklogView('proj-1');

    await waitFor(() => {
      expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
    });

    // Verify no inline breadcrumb div remains (old pattern had display:flex + gap:8 + link)
    const inlineDivs = container.querySelectorAll('div[style*="display: flex"]');
    // If any flex divs exist they should not contain bare anchor elements that are breadcrumbs
    inlineDivs.forEach((div) => {
      // Should not have a direct Link child that is a breadcrumb-styled inline link
      const links = div.querySelectorAll('a[style*="color: var(--color-text-secondary)"]');
      expect(links).toHaveLength(0);
    });
  });

  it('renders without error when wrapped in ActiveProjectProvider', async () => {
    // Verifies the component works with the ActiveProjectProvider context
    // (useSetActiveProject is called inside the component)
    renderBacklogView('proj-1');

    await waitFor(() => {
      expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
    });
  });
});
