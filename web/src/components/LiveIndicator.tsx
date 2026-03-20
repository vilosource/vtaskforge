import type { SSEStatus } from '../hooks/useSSE';

interface LiveIndicatorProps {
  status: SSEStatus;
}

export function LiveIndicator({ status }: LiveIndicatorProps) {
  if (status === 'connected') {
    return (
      <span className="live-indicator live-indicator--connected" aria-label="Live updates connected">
        <span className="live-indicator-dot" />
        Live
      </span>
    );
  }

  if (status === 'reconnecting') {
    return (
      <span className="live-indicator live-indicator--reconnecting" aria-label="Reconnecting to live updates">
        <span className="live-indicator-dot" />
        Reconnecting...
      </span>
    );
  }

  return (
    <span className="live-indicator live-indicator--disconnected" aria-label="Live updates offline">
      <span className="live-indicator-dot" />
      Offline
    </span>
  );
}
