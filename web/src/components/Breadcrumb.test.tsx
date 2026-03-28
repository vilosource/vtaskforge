import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Breadcrumb } from './Breadcrumb';

describe('Breadcrumb', () => {
  it('renders a nav element with aria-label', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Home', to: '/' }, { label: 'Current' }]} />
      </MemoryRouter>
    );
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
  });

  it('renders link segments as anchor elements with Tailwind classes', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Home', to: '/' }, { label: 'Current' }]} />
      </MemoryRouter>
    );
    const link = screen.getByRole('link', { name: 'Home' });
    expect(link).toHaveClass('font-medium');
  });

  it('renders last segment without to as span with bold text', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Home', to: '/' }, { label: 'Current Page' }]} />
      </MemoryRouter>
    );
    const current = screen.getByText('Current Page');
    expect(current.tagName).toBe('SPAN');
    expect(current).toHaveClass('font-bold');
  });

  it('renders separators between segments', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'A', to: '/a' }, { label: 'B', to: '/b' }, { label: 'C' }]} />
      </MemoryRouter>
    );
    const separators = screen.getAllByText('chevron_right');
    // 2 separators for 3 segments
    expect(separators).toHaveLength(2);
    separators.forEach((sep) => expect(sep).toHaveClass('material-symbols-outlined'));
  });

  it('renders single segment without any separator', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Only' }]} />
      </MemoryRouter>
    );
    expect(screen.queryByText('chevron_right')).toBeNull();
  });

  it('has flex layout class on nav', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Home' }]} />
      </MemoryRouter>
    );
    const nav = screen.getByRole('navigation');
    expect(nav).toHaveClass('flex');
  });
});
