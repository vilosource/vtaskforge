import { useParams, Link } from 'react-router-dom';
import { KanbanBoard } from './KanbanBoard';
import { useMilestone } from '../api/milestones';
import { useWorkplan } from '../api/tasks';
import { useProject } from '../api/projects';

export function BoardView() {
  const { id: projectId, wid: workplanId, milestoneId } = useParams<{ id: string; wid: string; milestoneId: string }>();
  const { data: project } = useProject(projectId);
  const { data: workplan } = useWorkplan(workplanId!);
  const { data: milestone } = useMilestone(milestoneId);

  if (!projectId || !workplanId || !milestoneId) {
    return <div className="error">Invalid project, workplan, or milestone ID.</div>;
  }

  return (
    <div>
      <div style={{ padding: '12px 24px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Link to={`/projects/${projectId}`} style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: 14 }}>
          {project?.name ?? 'Project'}
        </Link>
        <span style={{ color: 'var(--color-text-secondary)', fontSize: 14 }}>/</span>
        <Link to={`/projects/${projectId}/workplans/${workplanId}`} style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: 14 }}>
          {workplan?.name ?? 'Workplan'}
        </Link>
        {milestone && (
          <span style={{ color: 'var(--color-text)', fontSize: 14 }}>
            / {milestone.name}
          </span>
        )}
      </div>
      <KanbanBoard workplanId={workplanId} milestoneId={milestoneId} />
    </div>
  );
}
