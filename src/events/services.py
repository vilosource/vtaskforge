from events.models import TaskEvent


def record_event(task, event_type: str, data: dict = None,
                 trigger_source: str = "", actor=None) -> TaskEvent | None:
    """
    Create a TaskEvent for the given task.

    Args:
        task: The task this event belongs to.
        event_type: Event type (from EVENT_TYPE_CHOICES).
        data: Optional JSON data dict.
        trigger_source: Action label ("claim", "submit", "system", etc.).
        actor: User who triggered this event (None for system events).

    Returns the created TaskEvent on success, None on failure.
    Silent on failure to avoid disrupting the caller.
    """
    try:
        return TaskEvent.objects.create(
            task=task,
            event_type=event_type,
            data=data if data is not None else {},
            trigger_source=trigger_source,
            actor=actor,
        )
    except Exception:
        return None
