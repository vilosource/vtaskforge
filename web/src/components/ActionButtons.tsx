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

const btnBase = 'inline-flex items-center justify-center px-4 py-2 font-headline text-xs font-bold rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed';
const btnPrimary = `${btnBase} primary-gradient text-on-primary`;
const btnSecondary = `${btnBase} bg-surface-container-high text-on-surface`;
const btnDanger = `${btnBase} bg-error text-on-error`;
const btnSuccess = `${btnBase} bg-tertiary text-on-tertiary`;
const btnWarning = `${btnBase} bg-yellow-500 text-white`;

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
    <div className="flex flex-col gap-3">
      {/* Claim input */}
      {showClaimInput && (
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Agent ID"
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            className="bg-surface-container-low border-none rounded-lg px-3 py-1.5 text-sm font-body text-on-surface placeholder:text-on-surface-variant"
            aria-label="Agent ID"
          />
          <button
            onClick={() => claimMutation.mutate()}
            disabled={!agentId.trim() || claimMutation.isPending}
            className={btnPrimary}
          >
            {claimMutation.isPending ? 'Claiming...' : 'Confirm Claim'}
          </button>
          <button onClick={() => setShowClaimInput(false)} className={btnSecondary}>
            Cancel
          </button>
        </div>
      )}

      {/* Reason input */}
      {showReasonFor && (
        <div className="flex flex-wrap items-center gap-2">
          {isReviewStatus && (
            <input
              type="text"
              placeholder="Reviewer ID"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              className="bg-surface-container-low border-none rounded-lg px-3 py-1.5 text-sm font-body text-on-surface placeholder:text-on-surface-variant"
              aria-label="Reviewer ID"
            />
          )}
          <input
            type="text"
            placeholder="Reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="bg-surface-container-low border-none rounded-lg px-3 py-1.5 text-sm font-body text-on-surface placeholder:text-on-surface-variant"
            aria-label="Reason"
          />
          <button
            onClick={() => handleReasonSubmit(showReasonFor)}
            disabled={!reason.trim()}
            className={btnDanger}
          >
            Confirm
          </button>
          <button
            onClick={() => {
              setShowReasonFor(null);
              setReason('');
            }}
            className={btnSecondary}
          >
            Cancel
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {/* draft */}
        {status === 'draft' && (
          <button
            onClick={() => submitMutation.mutate()}
            disabled={submitMutation.isPending}
            className={btnPrimary}
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
              className={btnSuccess}
            >
              Approve
            </button>
            <button
              onClick={() => setShowReasonFor('reject')}
              className={btnDanger}
            >
              Reject
            </button>
            <button
              onClick={() => setShowReasonFor('request_changes')}
              className={btnWarning}
            >
              Request Changes
            </button>
          </>
        )}

        {/* todo */}
        {status === 'todo' && !showClaimInput && (
          <button
            onClick={() => setShowClaimInput(true)}
            className={btnPrimary}
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
              className={btnSuccess}
            >
              {completeMutation.isPending ? 'Completing...' : 'Complete'}
            </button>
            <button
              onClick={() => setShowReasonFor('fail')}
              className={btnDanger}
            >
              Fail
            </button>
            <button
              onClick={() => setShowReasonFor('block')}
              className={btnWarning}
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
            className={btnPrimary}
          >
            {unblockMutation.isPending ? 'Unblocking...' : 'Unblock'}
          </button>
        )}

        {/* changes_requested */}
        {status === 'changes_requested' && (
          <button
            onClick={() => resubmitMutation.mutate()}
            disabled={resubmitMutation.isPending}
            className={btnPrimary}
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
              className={btnPrimary}
            >
              Rewrite
            </button>
            <button
              onClick={() => unblockMutation.mutate()}
              disabled={unblockMutation.isPending}
              className={btnSecondary}
            >
              Back to pool
            </button>
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className={btnDanger}
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
              className={btnSecondary}
            >
              {deferMutation.isPending ? 'Deferring...' : 'Defer'}
            </button>
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className={btnDanger}
            >
              {cancelMutation.isPending ? 'Cancelling...' : 'Cancel'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
