import type { Task } from '../api/tasks';
import { useConsoleWidget } from '../contexts/ConsoleWidgetContext';

const BORDER_COLORS: Record<string, string> = {
  draft: 'border-l-outline',
  pending_start_review: 'border-l-yellow-500',
  pending_completion_review: 'border-l-yellow-500',
  todo: 'border-l-primary',
  doing: 'border-l-blue-600',
  changes_requested: 'border-l-yellow-500',
  needs_attention: 'border-l-error',
  blocked: 'border-l-error',
  done: 'border-l-tertiary',
  deferred: 'border-l-outline',
  cancelled: 'border-l-outline',
};

const BADGE_STYLES: Record<string, string> = {
  draft: 'bg-surface-container-highest text-on-surface-variant',
  pending_start_review: 'bg-yellow-100 text-yellow-800',
  pending_completion_review: 'bg-yellow-100 text-yellow-800',
  todo: 'bg-primary-fixed text-on-primary-fixed',
  doing: 'bg-blue-100 text-blue-800',
  changes_requested: 'bg-yellow-100 text-yellow-800',
  needs_attention: 'bg-error-container text-on-error-container',
  blocked: 'bg-error-container text-on-error-container',
  done: 'bg-tertiary-fixed text-on-tertiary-fixed',
  deferred: 'bg-surface-container-highest text-on-surface-variant',
  cancelled: 'bg-surface-container-highest text-on-surface-variant',
};

interface TaskCardProps {
  task: Task;
  onClick?: (task: Task) => void;
}

export function TaskCard({ task, onClick }: TaskCardProps) {
  const { open: openConsoleWidget } = useConsoleWidget();
  return (
    <div
      className={`bg-surface-container-lowest p-4 rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer border-l-[3px] ${BORDER_COLORS[task.status] ?? 'border-l-outline'}`}
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
      <div className="text-sm font-semibold text-on-surface mb-1">{task.title}</div>
      {task.execution_summary?.nl_summary?.one_liner && (
        <div className="text-xs text-on-surface-variant mb-2 line-clamp-1">{task.execution_summary.nl_summary.one_liner}</div>
      )}
      <div className="flex flex-wrap gap-2 items-center">
        <span className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase ${BADGE_STYLES[task.status] ?? 'bg-surface-container-highest text-on-surface-variant'}`}>
          {task.status}
        </span>
        {task.claimed_by && (
          <span className="bg-secondary-container text-on-secondary-container rounded px-2 py-0.5 text-[10px] font-medium">{task.claimed_by}</span>
        )}
        {task.milestone && (
          <span className="bg-tertiary-container text-on-tertiary-container rounded px-2 py-0.5 text-[10px] font-medium">{task.milestone}</span>
        )}
        {task.status === 'doing' && task.claimed_by && task.claimed_by_pod_name && (
          <button
            className="material-symbols-outlined text-primary text-sm ml-auto hover:text-primary/80 transition-colors"
            title="Open terminal"
            onClick={(e) => {
              e.stopPropagation();
              openConsoleWidget({ pod: task.claimed_by_pod_name!, command: 'bash' });
            }}
          >
            terminal
          </button>
        )}
        {task.status === 'doing' && task.claimed_by && !task.claimed_by_pod_name && (
          <span className="material-symbols-outlined text-primary text-sm ml-auto" title="Agent running">terminal</span>
        )}
      </div>
    </div>
  );
}
