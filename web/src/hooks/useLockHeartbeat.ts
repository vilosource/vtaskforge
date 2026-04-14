import { useEffect, useRef } from 'react';
import { checkLock } from '../api/bridge';

const DEFAULT_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

interface UseLockHeartbeatOptions {
  project: string | null;
  role: string;
  sessionId: string | null;
  enabled: boolean;
  intervalMs?: number;
  onExpired: () => void;
  onConflict: (heldBy: string) => void;
}

export function useLockHeartbeat({
  project,
  role,
  sessionId,
  enabled,
  intervalMs = DEFAULT_INTERVAL_MS,
  onExpired,
  onConflict,
}: UseLockHeartbeatOptions) {
  const onExpiredRef = useRef(onExpired);
  onExpiredRef.current = onExpired;
  const onConflictRef = useRef(onConflict);
  onConflictRef.current = onConflict;

  useEffect(() => {
    if (!enabled || !project || !sessionId) return;

    const check = async () => {
      try {
        const locks = await checkLock(project, role);
        if (locks.length === 0) {
          onExpiredRef.current();
        } else {
          const lock = locks[0];
          if (lock.session_id !== sessionId) {
            onConflictRef.current(lock.user);
          }
        }
      } catch {
        // Network error during heartbeat — don't treat as expiration,
        // could be transient. Next heartbeat will retry.
      }
    };

    const id = setInterval(check, intervalMs);
    return () => clearInterval(id);
  }, [enabled, project, role, sessionId, intervalMs]);
}
