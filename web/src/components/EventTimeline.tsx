import type { TaskEvent } from '../api/tasks';

interface EventTimelineProps {
  events: TaskEvent[];
}

function formatEventType(eventType: string): string {
  return eventType.replace(/_/g, ' ');
}

function formatTimestamp(ts: string): string {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function EventTimeline({ events }: EventTimelineProps) {
  const sorted = [...events].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );

  if (sorted.length === 0) {
    return <p className="event-timeline-empty">No events yet.</p>;
  }

  return (
    <ol className="event-timeline">
      {sorted.map((event) => (
        <li key={event.id} className="event-timeline-item">
          <span className="event-timeline-time">{formatTimestamp(event.created_at)}</span>
          <span className="event-timeline-type">{formatEventType(event.event_type)}</span>
          {event.event_type === 'status_changed' && (
            <span className="event-timeline-status-change">
              <span className="badge">{String(event.data.from)}</span>
              {' → '}
              <span className="badge">{String(event.data.to)}</span>
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}
