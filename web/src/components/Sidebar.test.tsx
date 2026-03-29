import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ActiveProjectProvider } from '../contexts/ActiveProjectContext';
import { Sidebar } from './Sidebar';

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderSidebar(initialEntry = '/', collapsed = false) {
  const onToggle = () => {};
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <ActiveProjectProvider>
          <Sidebar collapsed={collapsed} onToggle={onToggle} />
        </ActiveProjectProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Sidebar', () => {
  it('renders the brand link', () => {
    renderSidebar();
    expect(screen.getByText('VTaskForge')).toBeInTheDocument();
  });

  it('renders top-level navigation items', () => {
    renderSidebar();
    expect(screen.getByRole('link', { name: /Home/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Projects/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Agents/ })).toBeInTheDocument();
  });

  it('highlights the active nav item based on current path', () => {
    renderSidebar('/projects');
    const projectsLink = screen.getByRole('link', { name: /Projects/ });
    expect(projectsLink).toHaveClass('font-bold');
    expect(projectsLink).toHaveClass('text-blue-600');

    const homeLink = screen.getByRole('link', { name: /Home/ });
    expect(homeLink).not.toHaveClass('font-bold');
  });
});
