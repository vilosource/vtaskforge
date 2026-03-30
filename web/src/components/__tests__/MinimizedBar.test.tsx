import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { MinimizedBar } from '../MinimizedBar';

describe('MinimizedBar', () => {
  it('renders role and project name', () => {
    render(<MinimizedBar target={{ role: 'architect', project: 'my-project' }} onRestore={vi.fn()} />);
    expect(screen.getByText(/architect/i)).toBeInTheDocument();
    expect(screen.getByText(/my-project/i)).toBeInTheDocument();
  });

  it('click restores widget', async () => {
    const user = userEvent.setup();
    const onRestore = vi.fn();
    render(<MinimizedBar target={{ role: 'architect' }} onRestore={onRestore} />);

    await user.click(screen.getByTestId('minimized-bar'));
    expect(onRestore).toHaveBeenCalled();
  });
});
