import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { TaskCard } from '../TaskCard';

const mockOpen = vi.fn();
vi.mock('../../contexts/ConsoleWidgetContext', () => ({
  useConsoleWidget: () => ({ open: mockOpen }),
}));

function makeTask(overrides: Record<string, unknown> = {}) {
  return {
    id: 'task-1',
    title: 'Test Task',
    status: 'doing',
    milestone: '',
    workplan: '',
    project: 'proj-1',
    labels: [],
    claimed_by: 'agent-1',
    claimed_by_pod_name: 'pod-xyz',
    claimed_at: null,
    assigned_to: null,
    requires: [],
    description: '',
    acceptance_criteria: [],
    notes: [],
    spec: '',
    agent_model: '',
    test_command: {},
    judge: false,
    isolation: '',
    created_at: '2025-01-01',
    updated_at: '2025-01-01',
    ...overrides,
  };
}

describe('TaskCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('terminal icon click opens widget when pod_name available', async () => {
    const user = userEvent.setup();

    render(<TaskCard task={makeTask() as any} />);

    const terminalBtn = screen.getByTitle('Open terminal');
    await user.click(terminalBtn);

    expect(mockOpen).toHaveBeenCalledWith({ pod: 'pod-xyz', command: 'bash' });
  });
});
