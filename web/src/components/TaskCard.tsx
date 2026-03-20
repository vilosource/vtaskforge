import type { Task } from '../api/tasks';

const STATUS_BADGE_COLORS: Record<string, string> = {
  draft: 'badge-draft',
  pending_start_review: 'badge-review',
  pending_completion_review: 'badge-review',
  todo: 'badge-ready',
  doing: 'badge-in-progress',
  changes_requested: 'badge-attention',
  needs_attention: 'badge-attention',
  blocked: 'badge-attention',
  done: 'badge-done',
  deferred: 'badge-deferred',
  cancelled: 'badge-cancelled',
};

interface TaskCardProps {
  task: Task;
  onClick?: (task: Task) => void;
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  return (
    <div
      className="task-card"
      data-task-id={task.id}
      data-status={task.status}
      onClick={() => onClick?.(task)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onClick?.(task);
        }
      }}
    >
      <div className="task-card-title">{task.title}</div>
      <div className="task-card-meta">
        <span className={`badge ${STATUS_BADGE_COLORS[task.status] ?? ''}`}>
          {task.status}
        </span>
        {task.claimed_by && (
          <span className="task-card-agent">{task.claimed_by}</span>
        )}
        {task.phase && (
          <span className="task-card-phase">{task.phase}</span>
        )}
      </div>
    </div>
  );
}
