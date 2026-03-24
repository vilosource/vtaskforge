from events.models import TaskEvent


def record_event(task, event_type: str, data: dict = None, triggered_by: str = "") -> TaskEvent | None:
    """
    Create a TaskEvent for the given task.

    Returns the created TaskEvent on success, None on failure.
    Silent on failure to avoid disrupting the caller.
    """
    try:
        return TaskEvent.objects.create(
            task=task,
            event_type=event_type,
            data=data if data is not None else {},
            triggered_by=triggered_by,
        )
    except Exception:
        return None
