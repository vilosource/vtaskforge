import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TaskCard } from './TaskCard';
import type { Task } from '../api/tasks';

const baseTask: Task = {
  id: 'task-1',
  title: 'Implement login form',
  status: 'todo',
  phase: 'phase-1',
  workplan: 'wp-1',
  claimed_by: null,
  claimed_at: null,
  assigned_to: null,
  requires: [],
  description: 'Build the login form',
  acceptance_criteria: [],
  notes: [],
  spec: '',
  agent_model: '',
  test_command: {},
  judge: false,
  isolation: 'sequential',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

describe('TaskCard', () => {
  it('renders task title', () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.getByText('Implement login form')).toBeInTheDocument();
  });

  it('renders status badge', () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.getByText('todo')).toBeInTheDocument();
  });

  it('renders claimed_by when set', () => {
    const task = { ...baseTask, claimed_by: 'agent-7' };
    render(<TaskCard task={task} />);
    expect(screen.getByText('agent-7')).toBeInTheDocument();
  });

  it('does not render claimed_by when null', () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.queryByText('agent-7')).not.toBeInTheDocument();
  });

  it('has data-task-id attribute', () => {
    render(<TaskCard task={baseTask} />);
    const card = screen.getByRole('button');
    expect(card).toHaveAttribute('data-task-id', 'task-1');
  });

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<TaskCard task={baseTask} onClick={onClick} />);
    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledWith(baseTask);
  });

  it('calls onClick on Enter key', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<TaskCard task={baseTask} onClick={onClick} />);
    const card = screen.getByRole('button');
    card.focus();
    await user.keyboard('{Enter}');
    expect(onClick).toHaveBeenCalledWith(baseTask);
  });

  it('renders specific status badge for blocked status', () => {
    const task = { ...baseTask, status: 'blocked' };
    render(<TaskCard task={task} />);
    const badge = screen.getByText('blocked');
    expect(badge).toHaveClass('badge-attention');
  });

  it('renders specific status badge for pending_start_review', () => {
    const task = { ...baseTask, status: 'pending_start_review' };
    render(<TaskCard task={task} />);
    expect(screen.getByText('pending_start_review')).toBeInTheDocument();
  });

  it('renders phase', () => {
    render(<TaskCard task={baseTask} />);
    expect(screen.getByText('phase-1')).toBeInTheDocument();
  });
});
