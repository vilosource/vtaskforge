import { useParams, Link } from 'react-router-dom';
import { KanbanBoard } from './KanbanBoard';
import { useMilestone } from '../api/milestones';
import { useWorkplan } from '../api/tasks';

export function BoardView() {
  const { id, milestoneId } = useParams<{ id: string; milestoneId: string }>();
  const { data: milestone } = useMilestone(milestoneId);
  const { data: workplan } = useWorkplan(id!);

  if (!id || !milestoneId) {
    return <div className="error">Invalid workplan or milestone ID.</div>;
  }

  return (
    <div>
      <div style={{ padding: '12px 24px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Link to={`/workplans/${id}`} style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: 14 }}>
          {workplan?.name ?? 'Back'}
        </Link>
        {milestone && (
          <span style={{ color: 'var(--color-text)', fontSize: 14 }}>
            / {milestone.name}
          </span>
        )}
      </div>
      <KanbanBoard workplanId={id} milestoneId={milestoneId} />
    </div>
  );
}
