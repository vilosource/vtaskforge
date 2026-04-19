import { useState } from 'react';
import type { PriorTurn } from '../types/chat';

interface PriorHistoryPanelProps {
  turns: PriorTurn[];
  loading: boolean;
}

/**
 * Phase 9 — collapsed expander showing project-scoped architect history.
 *
 * The chat record belongs to the architect (a project-level resource), not
 * to any one user. We render prior user messages with their sender's
 * username, and assistant messages as "Architect". The whole section is
 * collapsed by default so the widget's primary affordance is "type your
 * next prompt" — expanding shows the shared project record.
 */
export function PriorHistoryPanel({ turns, loading }: PriorHistoryPanelProps) {
  const [expanded, setExpanded] = useState(false);
  if (loading) {
    return (
      <div
        data-testid="prior-history-loading"
        className="text-xs text-on-surface-variant/70 italic px-3 py-2"
      >
        Loading prior conversation...
      </div>
    );
  }
  if (!turns || turns.length === 0) {
    return null;
  }
  const userTurnCount = turns.filter((t) => t.role === 'user').length;
  return (
    <div data-testid="prior-history-panel" className="border-b border-outline-variant/40">
      <button
        type="button"
        data-testid="prior-history-toggle"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-surface-container-low/50 transition-colors"
        aria-expanded={expanded}
      >
        <span className="text-xs font-medium text-on-surface-variant">
          {expanded ? 'Hide' : 'View'} prior conversation ({userTurnCount}{' '}
          {userTurnCount === 1 ? 'message' : 'messages'})
        </span>
        <span
          className={`material-symbols-outlined text-sm text-on-surface-variant transition-transform ${
            expanded ? 'rotate-180' : ''
          }`}
        >
          expand_more
        </span>
      </button>
      {expanded && (
        <div data-testid="prior-history-content" className="px-3 pb-3 space-y-3 bg-surface-container-low/20">
          <p className="text-[10px] text-on-surface-variant/70 italic">
            Project-scoped architect log — conversations across all project members.
          </p>
          {turns.map((turn, i) => {
            const label =
              turn.role === 'assistant'
                ? 'Architect'
                : turn.username
                  ? turn.username
                  : 'Unknown user';
            return (
              <div
                key={`${turn.session_id}-${i}`}
                data-testid={`prior-history-turn-${i}`}
                className={`text-xs ${turn.role === 'user' ? 'opacity-90' : 'opacity-75'}`}
              >
                <div className="text-[10px] font-semibold text-on-surface-variant/80 mb-0.5">
                  {label}
                </div>
                <div className="whitespace-pre-wrap break-words text-on-surface-variant">
                  {turn.text}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
