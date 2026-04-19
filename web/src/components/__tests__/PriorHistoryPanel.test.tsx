import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { PriorHistoryPanel } from '../PriorHistoryPanel';
import type { PriorTurn } from '../../types/chat';

const TURNS: PriorTurn[] = [
  {
    role: 'user',
    text: 'alice says hi',
    timestamp: '2026-04-19T10:00:00Z',
    session_id: 'sid-1',
    username: 'alice',
  },
  {
    role: 'assistant',
    text: 'architect replies',
    timestamp: '2026-04-19T10:00:01Z',
    session_id: 'sid-1',
    username: null,
  },
  {
    role: 'user',
    text: 'bob follows up later',
    timestamp: '2026-04-19T11:00:00Z',
    session_id: 'sid-2',
    username: 'bob',
  },
  {
    role: 'assistant',
    text: 'architect replies again',
    timestamp: '2026-04-19T11:00:01Z',
    session_id: 'sid-2',
    username: null,
  },
];

describe('PriorHistoryPanel', () => {
  it('renders nothing when empty', () => {
    const { container } = render(<PriorHistoryPanel turns={[]} loading={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows loading state', () => {
    render(<PriorHistoryPanel turns={[]} loading={true} />);
    expect(screen.getByTestId('prior-history-loading')).toBeInTheDocument();
  });

  it('renders collapsed by default with user-message count', () => {
    render(<PriorHistoryPanel turns={TURNS} loading={false} />);
    // Banner visible; content hidden
    expect(screen.getByTestId('prior-history-toggle')).toHaveTextContent(/View prior conversation \(2 messages\)/);
    expect(screen.queryByTestId('prior-history-content')).toBeNull();
  });

  it('expands on click and shows turns with user labels', () => {
    render(<PriorHistoryPanel turns={TURNS} loading={false} />);
    fireEvent.click(screen.getByTestId('prior-history-toggle'));
    const content = screen.getByTestId('prior-history-content');
    expect(content).toBeInTheDocument();
    // User messages labeled with username, assistant labeled "Architect"
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
    const architectLabels = screen.getAllByText('Architect');
    expect(architectLabels.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('alice says hi')).toBeInTheDocument();
    expect(screen.getByText('architect replies')).toBeInTheDocument();
  });

  it('renders "Unknown user" for user messages missing username', () => {
    const orphan: PriorTurn[] = [
      { role: 'user', text: 'no attribution', timestamp: 'x', session_id: 's', username: null },
      { role: 'assistant', text: 'reply', timestamp: 'y', session_id: 's', username: null },
    ];
    render(<PriorHistoryPanel turns={orphan} loading={false} />);
    fireEvent.click(screen.getByTestId('prior-history-toggle'));
    expect(screen.getByText('Unknown user')).toBeInTheDocument();
  });

  it('singular message vs plural', () => {
    const one: PriorTurn[] = [
      { role: 'user', text: 'hi', timestamp: 't', session_id: 's', username: 'alice' },
    ];
    render(<PriorHistoryPanel turns={one} loading={false} />);
    expect(screen.getByTestId('prior-history-toggle')).toHaveTextContent('1 message');
  });
});
