import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DependencyChain } from './DependencyChain';
import type { TaskLink } from '../api/tasks';

function makeLink(overrides: Partial<TaskLink> = {}): TaskLink {
  return {
    id: 'link-1',
    source_type: 'task',
    source_id: 'source-1',
    source_title: 'Source Task',
    target_type: 'task',
    target_id: 'target-1',
    target_title: 'Target Task',
    link_type: 'depends_on',
    metadata: {},
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

function renderChain(props: Partial<React.ComponentProps<typeof DependencyChain>> = {}) {
  return render(
    <MemoryRouter>
      <DependencyChain
        taskId="current-task"
        taskTitle="Current Task"
        taskStatus="doing"
        upstreamLinks={[]}
        downstreamLinks={[]}
        {...props}
      />
    </MemoryRouter>,
  );
}

describe('DependencyChain', () => {
  it('returns null when no dependencies or blockers', () => {
    const { container } = renderChain();
    expect(container.innerHTML).toBe('');
  });

  it('renders upstream dependency', () => {
    renderChain({
      upstreamLinks: [makeLink({ target_id: 'dep-1', target_title: 'Dependency Task' })],
    });
    expect(screen.getByText('Dependency Task')).toBeInTheDocument();
    expect(screen.getByText('Current Task')).toBeInTheDocument();
  });

  it('renders downstream blocker', () => {
    renderChain({
      downstreamLinks: [makeLink({ source_id: 'blocked-1', source_title: 'Blocked Task' })],
    });
    expect(screen.getByText('Blocked Task')).toBeInTheDocument();
  });

  it('current task is not a link', () => {
    renderChain({
      upstreamLinks: [makeLink()],
    });
    const currentNode = screen.getByText('Current Task');
    expect(currentNode.tagName).not.toBe('A');
  });

  it('upstream nodes are clickable links', () => {
    renderChain({
      upstreamLinks: [makeLink({ target_id: 'dep-1', target_title: 'Dep Task' })],
    });
    const link = screen.getByText('Dep Task');
    expect(link.closest('a')).toHaveAttribute('href', '/tasks/dep-1');
  });

  it('truncates long titles', () => {
    renderChain({
      upstreamLinks: [makeLink({
        target_title: 'This is a very long task title that should be truncated',
      })],
    });
    expect(screen.getByText(/This is a very long task tit/)).toBeInTheDocument();
  });
});
