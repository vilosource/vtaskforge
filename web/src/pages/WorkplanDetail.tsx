import { useParams, Link } from 'react-router-dom';
import { useWorkplan } from '../api/tasks';
import { usePhases, usePhaseStats } from '../api/phases';
import { useSSE } from '../hooks/useSSE';
import { LiveIndicator } from '../components/LiveIndicator';

function PhaseCard({ phase, workplanId }: { phase: { id: string; name: string; status: string }; workplanId: string }) {
  const { data: stats } = usePhaseStats(phase.id);
  const total = stats?.total_tasks ?? 0;
  const done = stats?.by_status?.done ?? 0;
  const pct = stats?.completed_percentage ?? 0;

  const statusColor = phase.status === 'completed' ? '#4caf50'
    : phase.status === 'active' ? '#1976d2'
    : '#9e9e9e';

  return (
    <Link
      to={`/workplans/${workplanId}/phases/${phase.id}`}
      style={{
        display: 'block',
        padding: '16px 20px',
        background: 'white',
        borderRadius: 8,
        borderLeft: `4px solid ${statusColor}`,
        textDecoration: 'none',
        color: 'inherit',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
        transition: 'box-shadow 0.2s',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)'; }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 16 }}>{phase.name}</div>
          <div style={{ color: '#666', fontSize: 13, marginTop: 4 }}>
            {total} tasks &middot; {done} done
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{
            display: 'inline-block',
            padding: '2px 10px',
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 600,
            textTransform: 'uppercase',
            background: statusColor + '20',
            color: statusColor,
          }}>
            {phase.status}
          </div>
          <div style={{ marginTop: 8, width: 120, height: 6, background: '#e0e0e0', borderRadius: 3 }}>
            <div style={{
              width: `${pct}%`,
              height: '100%',
              background: statusColor,
              borderRadius: 3,
              transition: 'width 0.3s',
            }} />
          </div>
          <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{pct}%</div>
        </div>
      </div>
    </Link>
  );
}

export function WorkplanDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: workplan, isLoading: wpLoading } = useWorkplan(id!);
  const { data: phases, isLoading: phLoading } = usePhases(id!);
  const { status: sseStatus } = useSSE({
    url: `/v1/events/stream/?workplan=${id}`,
    onEvent: () => {},
    enabled: !!id,
  });

  if (wpLoading || phLoading) return <div style={{ padding: 40 }}>Loading...</div>;

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <Link to="/" style={{ color: '#666', textDecoration: 'none', fontSize: 14 }}>&larr; Workplans</Link>
          <h1 style={{ margin: '4px 0 0' }}>{workplan?.name || 'Workplan'}</h1>
          {workplan?.description && (
            <p style={{ color: '#666', margin: '4px 0 0' }}>{workplan.description}</p>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <LiveIndicator status={sseStatus} />
          <span style={{ color: '#888', fontSize: 14 }}>{phases?.length ?? 0} phases</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {phases && phases.length > 0 ? (
          phases.map((phase) => (
            <PhaseCard key={phase.id} phase={phase} workplanId={id!} />
          ))
        ) : (
          <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>No phases yet.</div>
        )}
      </div>
    </div>
  );
}
