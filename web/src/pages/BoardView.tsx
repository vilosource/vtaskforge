import { useParams, Link } from 'react-router-dom';
import { KanbanBoard } from './KanbanBoard';

export function BoardView() {
  const { id, phaseId } = useParams<{ id: string; phaseId: string }>();

  if (!id || !phaseId) {
    return <div className="error">Invalid workplan or phase ID.</div>;
  }

  return (
    <div>
      <div style={{ padding: '8px 16px' }}>
        <Link to={`/workplans/${id}`} style={{ color: '#666', textDecoration: 'none', fontSize: 14 }}>
          &larr; Back to phases
        </Link>
      </div>
      <KanbanBoard workplanId={id} phaseId={phaseId} />
    </div>
  );
}
