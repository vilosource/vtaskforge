import { useParams, Link } from 'react-router-dom';
import { KanbanBoard } from './KanbanBoard';
import { usePhase } from '../api/phases';
import { useWorkplan } from '../api/tasks';

export function BoardView() {
  const { id, phaseId } = useParams<{ id: string; phaseId: string }>();
  const { data: phase } = usePhase(phaseId);
  const { data: workplan } = useWorkplan(id!);

  if (!id || !phaseId) {
    return <div className="error">Invalid workplan or phase ID.</div>;
  }

  return (
    <div>
      <div style={{ padding: '12px 24px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Link to={`/workplans/${id}`} style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: 14 }}>
          {workplan?.name ?? 'Back'}
        </Link>
        {phase && (
          <span style={{ color: 'var(--color-text)', fontSize: 14 }}>
            / {phase.name}
          </span>
        )}
      </div>
      <KanbanBoard workplanId={id} phaseId={phaseId} />
    </div>
  );
}
