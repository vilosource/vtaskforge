import type { SSEStatus } from '../hooks/useSSE';

interface LiveIndicatorProps {
  status: SSEStatus;
}

export function LiveIndicator({ status }: LiveIndicatorProps) {
  if (status === 'connected') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-bold font-headline text-green-800" aria-label="Live updates connected">
        <span className="h-2 w-2 rounded-full bg-green-500" />
        Live
      </span>
    );
  }

  if (status === 'reconnecting') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-bold font-headline text-yellow-800" aria-label="Reconnecting to live updates">
        <span className="h-2 w-2 rounded-full bg-yellow-500 animate-pulse" />
        Reconnecting...
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-bold font-headline text-gray-500" aria-label="Live updates offline">
      <span className="h-2 w-2 rounded-full bg-gray-400" />
      Offline
    </span>
  );
}
