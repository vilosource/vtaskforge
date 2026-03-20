import { Link } from 'react-router-dom';
import { usePhaseStats } from '../api/phases';
import type { Phase } from '../api/phases';

interface PhasePipelineProps {
  phases: Phase[];
  workplanId: string;
}

const PHASES_PER_ROW = 4;

const STATUS_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  completed: { bg: '#e8f5e9', border: '#4caf50', text: '#2e7d32' },
  active: { bg: '#e3f2fd', border: '#1976d2', text: '#1565c0' },
  pending: { bg: '#f5f5f5', border: '#9e9e9e', text: '#616161' },
};

function PipelineNode({ phase, workplanId }: { phase: Phase; workplanId: string }) {
  const { data: stats } = usePhaseStats(phase.id);
  const total = stats?.total_tasks ?? 0;
  const done = stats?.by_status?.done ?? 0;
  const pct = stats?.completed_percentage ?? 0;
  const colors = STATUS_COLORS[phase.status] ?? STATUS_COLORS.pending;

  return (
    <Link
      to={`/workplans/${workplanId}/phases/${phase.id}`}
      style={{ textDecoration: 'none', flex: 1, minWidth: 0 }}
    >
      <div style={{
        padding: '10px 12px',
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: 8,
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s',
      }}>
        <div style={{
          fontWeight: 600, fontSize: 13, color: colors.text,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {phase.name}
        </div>
        <div style={{ fontSize: 11, color: '#666', marginTop: 3 }}>
          {done}/{total}
        </div>
        <div style={{ marginTop: 4, height: 3, background: '#e0e0e0', borderRadius: 2 }}>
          <div style={{
            width: `${pct}%`, height: '100%',
            background: colors.border, borderRadius: 2,
          }} />
        </div>
      </div>
    </Link>
  );
}

function HArrow({ reverse }: { reverse?: boolean }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      padding: '0 2px', color: '#bdbdbd', fontSize: 16, flexShrink: 0,
    }}>
      {reverse ? '\u2190' : '\u2192'}
    </div>
  );
}

function VConnector({ side }: { side: 'right' | 'left' }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: side === 'right' ? 'flex-end' : 'flex-start',
      padding: side === 'right' ? '0 24px 0 0' : '0 0 0 24px',
    }}>
      <div style={{
        width: 2, height: 20,
        background: '#bdbdbd',
        position: 'relative',
      }}>
        {/* Down arrow */}
        <div style={{
          position: 'absolute', bottom: -6, left: -4,
          width: 0, height: 0,
          borderLeft: '5px solid transparent',
          borderRight: '5px solid transparent',
          borderTop: '6px solid #bdbdbd',
        }} />
      </div>
    </div>
  );
}

export function PhasePipeline({ phases, workplanId }: PhasePipelineProps) {
  if (phases.length === 0) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>No phases yet.</div>;
  }

  // Split phases into rows
  const rows: Phase[][] = [];
  for (let i = 0; i < phases.length; i += PHASES_PER_ROW) {
    rows.push(phases.slice(i, i + PHASES_PER_ROW));
  }

  return (
    <div style={{ padding: '8px 0' }}>
      {rows.map((row, rowIndex) => {
        const isReversed = rowIndex % 2 === 1;
        const displayRow = isReversed ? [...row].reverse() : row;
        const isLastRow = rowIndex === rows.length - 1;

        return (
          <div key={rowIndex}>
            {/* Phase row */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 0,
            }}>
              {displayRow.map((phase, i) => (
                <div key={phase.id} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: 0 }}>
                  <PipelineNode phase={phase} workplanId={workplanId} />
                  {i < displayRow.length - 1 && <HArrow reverse={isReversed} />}
                </div>
              ))}
            </div>

            {/* Vertical connector to next row */}
            {!isLastRow && (
              <VConnector side={isReversed ? 'left' : 'right'} />
            )}
          </div>
        );
      })}
    </div>
  );
}
