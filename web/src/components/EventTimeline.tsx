import type { TaskEvent } from '../api/tasks';

interface EventTimelineProps {
  events: TaskEvent[];
}

function formatEventType(eventType: string): string {
  return eventType.replace(/_/g, ' ');
}

function formatTimestamp(ts: string): string {
  try {
    const date = new Date(ts);
    if (isNaN(date.getTime())) return ts;
    return date.toLocaleString();
  } catch {
    return ts;
  }
}

export function EventTimeline({ events }: EventTimelineProps) {
  const sorted = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  );

  if (sorted.length === 0) {
    return <p className="text-sm text-on-surface-variant font-body italic">No events yet.</p>;
  }

  return (
    <ol className="relative border-l-2 border-outline-variant ml-3 flex flex-col gap-0">
      {sorted.map((event) => (
        <li key={event.id} className="relative pl-6 pb-6 last:pb-0">
          <span className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full bg-primary" />
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-xs font-body text-on-surface-variant">{formatTimestamp(event.timestamp)}</span>
            <span className="text-sm font-headline font-bold text-on-surface capitalize">{formatEventType(event.event_type)}</span>
            {event.event_type === 'status_changed' && (
              <span className="inline-flex items-center gap-1 text-xs font-body">
                <span className="inline-flex items-center rounded-full bg-surface-container-high px-2 py-0.5 text-on-surface-variant">{String(event.data.from)}</span>
                {' \u2192 '}
                <span className="inline-flex items-center rounded-full bg-surface-container-high px-2 py-0.5 text-on-surface-variant">{String(event.data.to)}</span>
              </span>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
