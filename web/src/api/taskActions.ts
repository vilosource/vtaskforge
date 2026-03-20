import { apiPost } from './client';

export const submitTask = (id: string) => apiPost(`/v1/tasks/${id}/submit/`);
export const claimTask = (id: string, agentId: string) =>
  apiPost(`/v1/tasks/${id}/claim/`, { agent_id: agentId });
export const completeTask = (id: string) => apiPost(`/v1/tasks/${id}/complete/`);
export const failTask = (id: string, reason: string) =>
  apiPost(`/v1/tasks/${id}/fail/`, { reason });
export const blockTask = (id: string, reason: string) =>
  apiPost(`/v1/tasks/${id}/block/`, { reason });
export const unblockTask = (id: string) => apiPost(`/v1/tasks/${id}/unblock/`);
export const deferTask = (id: string) => apiPost(`/v1/tasks/${id}/defer/`);
export const cancelTask = (id: string) => apiPost(`/v1/tasks/${id}/cancel/`);
export const resubmitTask = (id: string) => apiPost(`/v1/tasks/${id}/resubmit/`);
export const addNote = (id: string, text: string, actorId: string) =>
  apiPost(`/v1/tasks/${id}/notes/`, { text, actor_id: actorId });

// Review actions
export const approveTask = (id: string, reviewerId: string) =>
  apiPost(`/v1/tasks/${id}/reviews/`, {
    decision: 'approved',
    reviewer_id: reviewerId,
    reviewer_type: 'human',
  });
export const rejectTask = (id: string, reviewerId: string, reason: string) =>
  apiPost(`/v1/tasks/${id}/reviews/`, {
    decision: 'rejected',
    reason,
    reviewer_id: reviewerId,
    reviewer_type: 'human',
  });
export const requestChanges = (id: string, reviewerId: string, reason: string) =>
  apiPost(`/v1/tasks/${id}/reviews/`, {
    decision: 'changes_requested',
    reason,
    reviewer_id: reviewerId,
    reviewer_type: 'human',
  });
