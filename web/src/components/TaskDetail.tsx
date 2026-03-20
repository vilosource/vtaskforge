import { useEffect, useCallback } from 'react';
import { useTaskDetail } from '../api/tasks';
import { EventTimeline } from './EventTimeline';
import { ActionButtons } from './ActionButtons';
import { AddNoteForm } from './AddNoteForm';

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
            <button
              className="task-detail-close"
              onClick={onClose}
              aria-label="Close"
            >
              ✕
            </button>
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
            {/* Description */}
            {task.description && (
              <section className="task-detail-section">
                <h3>Description</h3>
                <p className="task-detail-description">{task.description}</p>
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

            {/* Assignment */}
            <section className="task-detail-section">
              <h3>Assignment</h3>
              <dl className="task-detail-assignment">
                <dt>Claimed by</dt>
                <dd>{task.claimed_by ?? '—'}</dd>
                <dt>Assigned to</dt>
                <dd>{task.assigned_to ?? '—'}</dd>
                {task.requires.length > 0 && (
                  <>
                    <dt>Requires</dt>
                    <dd>{task.requires.join(', ')}</dd>
                  </>
                )}
              </dl>
            </section>

            {/* Links */}
            {task.links && task.links.length > 0 && (
              <section className="task-detail-section">
                <h3>Links</h3>
                <ul className="task-detail-links">
                  {task.links.map((link) => (
                    <li key={link.id} className="task-detail-link-item">
                      <span className="badge">{link.link_type}</span>
                      {' '}
                      <span>{link.target_id}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Reviews */}
            {task.reviews && task.reviews.length > 0 && (
              <section className="task-detail-section">
                <h3>Reviews</h3>
                <ul className="task-detail-reviews">
                  {task.reviews.map((review) => (
                    <li key={review.id} className="task-detail-review-item">
                      <span className="badge">{review.decision}</span>
                      {' '}
                      <span>by {review.reviewer_id}</span>
                      {review.reason && <span> — {review.reason}</span>}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Event timeline */}
            <section className="task-detail-section">
              <h3>Event Timeline</h3>
              <EventTimeline events={task.events ?? []} />
            </section>

            {/* Notes */}
            <section className="task-detail-section">
              <h3>Notes</h3>
              {task.notes && task.notes.length > 0 ? (
                <ul className="task-detail-notes">
                  {task.notes.map((note, i) => {
                    const noteObj = note as unknown as { id?: string; text?: string; actor_id?: string; created_at?: string };
                    return (
                      <li key={noteObj.id ?? i} className="task-detail-note-item">
                        {noteObj.actor_id && (
                          <span className="note-actor">{noteObj.actor_id}: </span>
                        )}
                        <span>{noteObj.text ?? String(note)}</span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="task-detail-no-notes">No notes yet.</p>
              )}
              <AddNoteForm taskId={task.id} />
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
