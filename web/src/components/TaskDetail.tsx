import { useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useTaskDetail } from '../api/tasks';
import { ActionButtons } from './ActionButtons';

interface TaskDetailProps {
  taskId: string | null;
  onClose: () => void;
}

export function TaskDetail({ taskId, onClose }: TaskDetailProps) {
  const { data: task, isLoading, isError } = useTaskDetail(taskId);

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
      className="task-detail-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Task detail"
    >
      <div className="task-detail-modal">
        {/* Header */}
        <div className="task-detail-header">
          <div className="task-detail-title-row">
            {task && <h2 className="task-detail-title">{task.title}</h2>}
            {isLoading && <h2 className="task-detail-title">Loading...</h2>}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              {task && (
                <Link
                  to={`/tasks/${task.id}`}
                  style={{
                    fontSize: 13,
                    color: '#1976d2',
                    textDecoration: 'none',
                    whiteSpace: 'nowrap',
                  }}
                  onClick={onClose}
                >
                  Open full view →
                </Link>
              )}
              <button
                className="task-detail-close"
                onClick={onClose}
                aria-label="Close"
              >
                ✕
              </button>
            </div>
          </div>
          {task && (
            <span className="badge task-detail-status">{task.status}</span>
          )}
        </div>

        {isLoading && (
          <div className="task-detail-loading">Loading task details...</div>
        )}

        {isError && (
          <div className="task-detail-error" role="alert">
            Failed to load task details.
          </div>
        )}

        {task && (
          <div className="task-detail-body">
            {/* Description (truncated) */}
            {truncatedDescription && (
              <section className="task-detail-section">
                <h3>Description</h3>
                <p className="task-detail-description">{truncatedDescription}</p>
              </section>
            )}

            {/* Acceptance criteria */}
            {task.acceptance_criteria.length > 0 && (
              <section className="task-detail-section">
                <h3>Acceptance Criteria</h3>
                <ul className="task-detail-criteria">
                  {task.acceptance_criteria.map((criterion, i) => (
                    <li key={i}>{criterion}</li>
                  ))}
                </ul>
              </section>
            )}

            {/* Dependencies summary */}
            {dependsOnLinks.length > 0 && (
              <section className="task-detail-section">
                <h3>Dependencies</h3>
                <ul className="task-detail-links">
                  {dependsOnLinks.map((link) => (
                    <li key={link.id} className="task-detail-link-item">
                      <span className="badge">depends_on</span>
                      {' '}
                      <span>{link.target_title ?? link.target_id}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Assignment */}
            <section className="task-detail-section">
              <h3>Assignment</h3>
              <dl className="task-detail-assignment">
                <dt>Claimed by</dt>
                <dd>{task.claimed_by ?? '\u2014'}</dd>
                <dt>Assigned to</dt>
                <dd>{task.assigned_to ?? '\u2014'}</dd>
              </dl>
            </section>

            {/* Actions */}
            <section className="task-detail-section">
              <h3>Actions</h3>
              <ActionButtons taskId={task.id} status={task.status} />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
