from tasks.state_machine import TERMINAL_STATUSES


def maybe_complete_phase(task):
    """Auto-complete a phase when all its tasks reach terminal status.

    Returns the phase if it was completed, None otherwise.
    """
    phase = getattr(task, "phase", None)
    if phase is None:
        return None

    if phase.status != "active":
        return None

    if not phase.tasks.exists():
        return None

    if phase.tasks.exclude(status__in=TERMINAL_STATUSES).exists():
        return None

    phase.status = "completed"
    phase.save(update_fields=["status", "updated_at"])
    return phase
