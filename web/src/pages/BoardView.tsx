import { useParams } from 'react-router-dom';
import { KanbanBoard } from './KanbanBoard';
import { useMilestone } from '../api/milestones';
import { useWorkplan } from '../api/tasks';
import { useProject } from '../api/projects';
import { Breadcrumb } from '../components/Breadcrumb';
import { useSetActiveProject } from '../contexts/ActiveProjectContext';

export function BoardView() {
  const { id: projectId, wid: workplanId, milestoneId } = useParams<{ id: string; wid: string; milestoneId: string }>();
  useSetActiveProject(projectId);
  const { data: project } = useProject(projectId);
  const { data: workplan } = useWorkplan(workplanId!);
  const { data: milestone } = useMilestone(milestoneId);

  if (!projectId || !workplanId || !milestoneId) {
    return <div className="flex items-center justify-center h-64 text-error">Invalid project, workplan, or milestone ID.</div>;
  }

  return (
    <div>
      <div className="px-6">
        <Breadcrumb segments={[
          { label: project?.name ?? 'Project', to: `/projects/${projectId}` },
          { label: workplan?.name ?? 'Workplan', to: `/projects/${projectId}/workplans/${workplanId}` },
          ...(milestone ? [{ label: milestone.name }] : [])
        ]} />
      </div>
      <KanbanBoard workplanId={workplanId} milestoneId={milestoneId} />
    </div>
  );
}
