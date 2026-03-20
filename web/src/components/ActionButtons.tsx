import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  submitTask,
  claimTask,
  completeTask,
  failTask,
  blockTask,
  unblockTask,
  deferTask,
  cancelTask,
  resubmitTask,
  approveTask,
  rejectTask,
  requestChanges,
} from '../api/taskActions';

const TERMINAL_STATUSES = ['done', 'cancelled'];

interface ActionButtonsProps {
  taskId: string;
  status: string;
  onSuccess?: () => void;
}

export function ActionButtons({ taskId, status, onSuccess }: ActionButtonsProps) {
  const queryClient = useQueryClient();
  const [agentId, setAgentId] = useState('');
  const [showClaimInput, setShowClaimInput] = useState(false);
  const [reason, setReason] = useState('');
  const [showReasonFor, setShowReasonFor] = useState<string | null>(null);
  const [reviewerId, setReviewerId] = useState('human');

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['tasks'] });
    queryClient.invalidateQueries({ queryKey: ['task', taskId] });
    onSuccess?.();
  }

  const submitMutation = useMutation({
    mutationFn: () => submitTask(taskId),
    onSuccess: invalidate,
  });

  const claimMutation = useMutation({
    mutationFn: () => claimTask(taskId, agentId),
    onSuccess: () => {
      setShowClaimInput(false);
      setAgentId('');
      invalidate();
    },
  });

  const completeMutation = useMutation({
    mutationFn: () => completeTask(taskId),
    onSuccess: invalidate,
  });

  const failMutation = useMutation({
    mutationFn: () => failTask(taskId, reason),
    onSuccess: () => {
      setShowReasonFor(null);
      setReason('');
      invalidate();
    },
  });

  const blockMutation = useMutation({
    mutationFn: () => blockTask(taskId, reason),
    onSuccess: () => {
      setShowReasonFor(null);
      setReason('');
      invalidate();
    },
  });

  const unblockMutation = useMutation({
    mutationFn: () => unblockTask(taskId),
    onSuccess: invalidate,
  });

  const deferMutation = useMutation({
    mutationFn: () => deferTask(taskId),
    onSuccess: invalidate,
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelTask(taskId),
    onSuccess: invalidate,
  });

  const resubmitMutation = useMutation({
    mutationFn: () => resubmitTask(taskId),
    onSuccess: invalidate,
  });

  const approveMutation = useMutation({
    mutationFn: () => approveTask(taskId, reviewerId),
    onSuccess: invalidate,
  });

  const rejectMutation = useMutation({
    mutationFn: () => rejectTask(taskId, reviewerId, reason),
    onSuccess: () => {
      setShowReasonFor(null);
      setReason('');
      invalidate();
    },
  });

  const requestChangesMutation = useMutation({
    mutationFn: () => requestChanges(taskId, reviewerId, reason),
    onSuccess: () => {
      setShowReasonFor(null);
      setReason('');
      invalidate();
    },
  });

  if (TERMINAL_STATUSES.includes(status)) {
    return null;
  }

  const isReviewStatus =
    status === 'pending_start_review' || status === 'pending_completion_review';
  const isNonTerminal = !TERMINAL_STATUSES.includes(status);

  function handleReasonSubmit(action: string) {
    if (action === 'fail') failMutation.mutate();
    else if (action === 'block') blockMutation.mutate();
    else if (action === 'reject') rejectMutation.mutate();
    else if (action === 'request_changes') requestChangesMutation.mutate();
  }

  return (
    <div className="action-buttons">
      {/* Claim input */}
      {showClaimInput && (
        <div className="action-input-group">
          <input
            type="text"
            placeholder="Agent ID"
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            className="action-input"
            aria-label="Agent ID"
          />
          <button
            onClick={() => claimMutation.mutate()}
            disabled={!agentId.trim() || claimMutation.isPending}
            className="btn btn-primary"
          >
            {claimMutation.isPending ? 'Claiming...' : 'Confirm Claim'}
          </button>
          <button onClick={() => setShowClaimInput(false)} className="btn btn-secondary">
            Cancel
          </button>
        </div>
      )}

      {/* Reason input */}
      {showReasonFor && (
        <div className="action-input-group">
          {isReviewStatus && (
            <input
              type="text"
              placeholder="Reviewer ID"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              className="action-input"
              aria-label="Reviewer ID"
            />
          )}
          <input
            type="text"
            placeholder="Reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="action-input"
            aria-label="Reason"
          />
          <button
            onClick={() => handleReasonSubmit(showReasonFor)}
            disabled={!reason.trim()}
            className="btn btn-danger"
          >
            Confirm
          </button>
          <button
            onClick={() => {
              setShowReasonFor(null);
              setReason('');
            }}
            className="btn btn-secondary"
          >
            Cancel
          </button>
        </div>
      )}

      <div className="action-buttons-row">
        {/* draft */}
        {status === 'draft' && (
          <button
            onClick={() => submitMutation.mutate()}
            disabled={submitMutation.isPending}
            className="btn btn-primary"
          >
            {submitMutation.isPending ? 'Submitting...' : 'Submit'}
          </button>
        )}

        {/* pending_start_review / pending_completion_review */}
        {isReviewStatus && (
          <>
            <button
              onClick={() => approveMutation.mutate()}
              disabled={approveMutation.isPending}
              className="btn btn-success"
            >
              Approve
            </button>
            <button
              onClick={() => setShowReasonFor('reject')}
              className="btn btn-danger"
            >
              Reject
            </button>
            <button
              onClick={() => setShowReasonFor('request_changes')}
              className="btn btn-warning"
            >
              Request Changes
            </button>
          </>
        )}

        {/* todo */}
        {status === 'todo' && !showClaimInput && (
          <button
            onClick={() => setShowClaimInput(true)}
            className="btn btn-primary"
          >
            Claim
          </button>
        )}

        {/* doing */}
        {status === 'doing' && (
          <>
            <button
              onClick={() => completeMutation.mutate()}
              disabled={completeMutation.isPending}
              className="btn btn-success"
            >
              {completeMutation.isPending ? 'Completing...' : 'Complete'}
            </button>
            <button
              onClick={() => setShowReasonFor('fail')}
              className="btn btn-danger"
            >
              Fail
            </button>
            <button
              onClick={() => setShowReasonFor('block')}
              className="btn btn-warning"
            >
              Block
            </button>
          </>
        )}

        {/* blocked */}
        {status === 'blocked' && (
          <button
            onClick={() => unblockMutation.mutate()}
            disabled={unblockMutation.isPending}
            className="btn btn-primary"
          >
            {unblockMutation.isPending ? 'Unblocking...' : 'Unblock'}
          </button>
        )}

        {/* changes_requested */}
        {status === 'changes_requested' && (
          <button
            onClick={() => resubmitMutation.mutate()}
            disabled={resubmitMutation.isPending}
            className="btn btn-primary"
          >
            {resubmitMutation.isPending ? 'Resubmitting...' : 'Resubmit'}
          </button>
        )}

        {/* needs_attention */}
        {status === 'needs_attention' && (
          <>
            <button
              onClick={() => submitMutation.mutate()}
              disabled={submitMutation.isPending}
              className="btn btn-primary"
            >
              Rewrite
            </button>
            <button
              onClick={() => unblockMutation.mutate()}
              disabled={unblockMutation.isPending}
              className="btn btn-secondary"
            >
              Back to pool
            </button>
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="btn btn-danger"
            >
              Cancel
            </button>
          </>
        )}

        {/* Any non-terminal: Defer and Cancel (except needs_attention which already has Cancel,
            and deferred/cancelled which are terminal) */}
        {isNonTerminal && status !== 'needs_attention' && status !== 'deferred' && (
          <>
            <button
              onClick={() => deferMutation.mutate()}
              disabled={deferMutation.isPending}
              className="btn btn-secondary"
            >
              {deferMutation.isPending ? 'Deferring...' : 'Defer'}
            </button>
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="btn btn-danger"
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Cancel'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
