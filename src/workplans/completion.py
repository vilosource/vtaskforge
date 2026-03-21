from tasks.state_machine import TERMINAL_STATUSES


def maybe_complete_milestone(task):
    """Auto-complete a milestone when all its tasks reach terminal status.

    Returns the milestone if it was completed, None otherwise.
    """
    milestone = getattr(task, "milestone", None)
    if milestone is None:
        return None

    if milestone.status != "active":
        return None

    if not milestone.tasks.exists():
        return None

    if milestone.tasks.exclude(status__in=TERMINAL_STATUSES).exists():
        return None

    milestone.status = "completed"
    milestone.save(update_fields=["status", "updated_at"])
    return milestone
