import { useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTaskDetail, useWorkplan } from '../api/tasks';
import { useProject } from '../api/projects';
import { useMilestone } from '../api/milestones';
import { ActionButtons } from './ActionButtons';

interface TaskDetailProps {
  taskId: string | null;
  onClose: () => void;
}

const statusColor: Record<string, string> = {
  done: 'bg-tertiary/10 text-tertiary',
  doing: 'bg-primary/10 text-primary',
  todo: 'bg-primary-fixed text-on-primary-fixed',
  draft: 'bg-surface-container-high text-on-surface-variant',
  blocked: 'bg-error-container text-on-error-container',
  needs_attention: 'bg-error-container/60 text-error',
  cancelled: 'bg-surface-container-high text-on-surface-variant',
};

function statusBadge(status: string) {
  return statusColor[status] ?? statusColor.draft;
}

export function TaskDetail({ taskId, onClose }: TaskDetailProps) {
  const { data: task, isLoading, isError } = useTaskDetail(taskId);
  const { data: project } = useProject(task?.project);
  const { data: workplan } = useWorkplan(task?.workplan ?? '');
  const { data: milestone } = useMilestone(task?.milestone);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (!taskId) return;
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [taskId, handleKeyDown]);

  if (!taskId) return null;

  const dependsOnLinks = (task?.links ?? []).filter(l => l.link_type === 'depends_on');
  const truncatedDescription = task?.description
    ? task.description.length > 200
      ? task.description.slice(0, 200) + '...'
      : task.description
    : '';

  return (
    <div
      className="fixed inset-0 bg-black/45 flex items-start justify-center z-50 p-8 overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Task detail"
    >
      <div className="bg-surface-container-lowest rounded-xl shadow-2xl w-full max-w-[700px] max-h-[90vh] overflow-hidden flex flex-col relative my-auto">
        {/* Header */}
        <div className="p-5 border-b border-outline-variant/20 flex-shrink-0">
          {task && (
            <div className="flex items-center gap-1 text-xs mb-1">
              {project && <Link to={`/projects/${task.project}`} onClick={onClose} className="text-on-surface-variant hover:underline">{project.name}</Link>}
              {workplan && <><span className="text-on-surface-variant">/</span><Link to={`/projects/${task.project}/workplans/${task.workplan}`} onClick={onClose} className="text-on-surface-variant hover:underline">{workplan.name}</Link></>}
              {milestone && <><span className="text-on-surface-variant">/</span><Link to={`/projects/${task.project}/workplans/${task.workplan}/milestones/${task.milestone}`} onClick={onClose} className="text-on-surface-variant hover:underline">{milestone.name}</Link></>}
            </div>
          )}
          <div className="flex items-start gap-3 mb-2">
            {task && <h2 className="flex-1 text-lg font-semibold leading-snug text-on-surface">{task.title}</h2>}
            {isLoading && <h2 className="flex-1 text-lg font-semibold leading-snug text-on-surface-variant">Loading...</h2>}
            <div className="flex items-center gap-2 flex-shrink-0">
              {task && (
                <Link
                  to={`/tasks/${task.id}`}
                  className="text-[13px] text-primary hover:underline whitespace-nowrap"
                  onClick={onClose}
                >
                  Open full view &rarr;
                </Link>
              )}
              <button
                className="w-10 h-10 rounded-lg border border-outline-variant/30 flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface transition-colors cursor-pointer flex-shrink-0"
                onClick={onClose}
                aria-label="Close"
              >
                &#x2715;
              </button>
            </div>
          </div>
          {task && (
            <span className={`inline-block rounded-full px-3 py-0.5 text-xs font-semibold ${statusBadge(task.status)}`}>{task.status}</span>
          )}
        </div>

        {isLoading && (
          <div className="flex items-center gap-3 p-6 text-on-surface-variant text-sm">
            <span className="inline-block w-4 h-4 border-2 border-outline-variant border-t-primary rounded-full animate-spin flex-shrink-0" />
            Loading task details...
          </div>
        )}

        {isError && (
          <div className="mx-6 mt-4 px-4 py-3 bg-error-container border border-error/20 rounded-lg text-on-error-container text-sm" role="alert">
            Failed to load task details.
          </div>
        )}

        {task && (
          <div className="overflow-y-auto p-6 flex-1">
            {/* Description (truncated) */}
            {truncatedDescription && (
              <section className="mb-5 pb-5 border-b border-outline-variant/20">
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2.5">Description</h3>
                <p className="text-sm text-on-surface whitespace-pre-wrap leading-relaxed">{truncatedDescription}</p>
              </section>
            )}

            {/* Acceptance criteria */}
            {task.acceptance_criteria.length > 0 && (
              <section className="mb-5 pb-5 border-b border-outline-variant/20">
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2.5">Acceptance Criteria</h3>
                <ul className="space-y-1.5">
                  {task.acceptance_criteria.map((criterion, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-on-surface">
                      <span className="material-symbols-outlined text-[18px] mt-0.5 text-outline-variant">radio_button_unchecked</span>
                      <span>{criterion}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Dependencies summary */}
            {dependsOnLinks.length > 0 && (
              <section className="mb-5 pb-5 border-b border-outline-variant/20">
                <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2.5">Dependencies</h3>
                <ul className="space-y-1.5">
                  {dependsOnLinks.map((link) => (
                    <li key={link.id} className="flex items-baseline gap-2 text-sm">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold bg-surface-container-high text-on-surface-variant`}>depends_on</span>
                      <span className="text-on-surface">{link.target_title ?? link.target_id}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Assignment */}
            <section className="mb-5 pb-5 border-b border-outline-variant/20">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2.5">Assignment</h3>
              <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 text-sm">
                <dt className="text-on-surface-variant font-medium">Claimed by</dt>
                <dd className="text-on-surface font-mono text-[13px]">{task.claimed_by ?? '\u2014'}</dd>
                <dt className="text-on-surface-variant font-medium">Assigned to</dt>
                <dd className="text-on-surface font-mono text-[13px]">{task.assigned_to ?? '\u2014'}</dd>
              </dl>
            </section>

            {/* Actions */}
            <section>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant mb-2.5">Actions</h3>
              <ActionButtons taskId={task.id} status={task.status} />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
