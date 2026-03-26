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

  it('renders link segments as anchor elements with breadcrumb-link class', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Home', to: '/' }, { label: 'Current' }]} />
      </MemoryRouter>
    );
    const link = screen.getByRole('link', { name: 'Home' });
    expect(link).toHaveClass('breadcrumb-link');
  });

  it('renders last segment without to as span with breadcrumb-current class', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Home', to: '/' }, { label: 'Current Page' }]} />
      </MemoryRouter>
    );
    const current = screen.getByText('Current Page');
    expect(current.tagName).toBe('SPAN');
    expect(current).toHaveClass('breadcrumb-current');
  });

  it('renders separators between segments', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'A', to: '/a' }, { label: 'B', to: '/b' }, { label: 'C' }]} />
      </MemoryRouter>
    );
    const separators = screen.getAllByText('/');
    // 2 separators for 3 segments
    expect(separators).toHaveLength(2);
    separators.forEach((sep) => expect(sep).toHaveClass('breadcrumb-separator'));
  });

  it('renders single segment without any separator', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Only' }]} />
      </MemoryRouter>
    );
    expect(screen.queryByText('/')).toBeNull();
  });

  it('has breadcrumb class on nav', () => {
    render(
      <MemoryRouter>
        <Breadcrumb segments={[{ label: 'Home' }]} />
      </MemoryRouter>
    );
    const nav = screen.getByRole('navigation');
    expect(nav).toHaveClass('breadcrumb');
  });
});
