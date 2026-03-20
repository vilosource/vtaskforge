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
      <div style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Link to={`/workplans/${id}`} style={{ color: '#666', textDecoration: 'none', fontSize: 14 }}>
          &larr; {workplan?.name ?? 'Back'}
        </Link>
        {phase && (
          <span style={{ color: '#333', fontSize: 14, fontWeight: 600 }}>
            / {phase.name}
          </span>
        )}
      </div>
      <KanbanBoard workplanId={id} phaseId={phaseId} />
    </div>
  );
}
