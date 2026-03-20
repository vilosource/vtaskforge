import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { usePhaseStats } from '../api/phases';
import type { Phase } from '../api/phases';

interface PhasePipelineProps {
  phases: Phase[];
  workplanId: string;
}

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
      style={{ textDecoration: 'none' }}
    >
      <div style={{
        minWidth: 160,
        padding: '12px 16px',
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: 8,
        textAlign: 'center',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s',
      }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: colors.text }}>{phase.name}</div>
        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
          {done}/{total} tasks
        </div>
        <div style={{ marginTop: 6, height: 4, background: '#e0e0e0', borderRadius: 2 }}>
          <div style={{
            width: `${pct}%`,
            height: '100%',
            background: colors.border,
            borderRadius: 2,
            transition: 'width 0.3s',
          }} />
        </div>
        <div style={{
          marginTop: 4, fontSize: 11, fontWeight: 600,
          textTransform: 'uppercase', color: colors.text,
        }}>
          {phase.status}
        </div>
      </div>
    </Link>
  );
}

function Arrow() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      padding: '0 4px', color: '#bdbdbd', fontSize: 20,
    }}>
      →
    </div>
  );
}

export function PhasePipeline({ phases, workplanId }: PhasePipelineProps) {
  if (phases.length === 0) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>No phases yet.</div>;
  }

  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      overflowX: 'auto', padding: '16px 0', gap: 0,
    }}>
      {phases.map((phase, i) => (
        <Fragment key={phase.id}>
          <PipelineNode phase={phase} workplanId={workplanId} />
          {i < phases.length - 1 && <Arrow />}
        </Fragment>
      ))}
    </div>
  );
}
