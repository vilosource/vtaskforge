from tasks.state_machine import TERMINAL_STATUSES


def maybe_complete_milestone(task):
    """Auto-complete a milestone when all its tasks reach terminal status.

    Completes milestones in both 'active' and 'pending' states. If all
    tasks are terminal, the milestone is done regardless of whether it
    was formally activated.

    Returns the milestone if it was completed, None otherwise.
    """
    milestone = getattr(task, "milestone", None)
    if milestone is None:
        return None

    if milestone.status not in ("active", "pending"):
        return None

    if not milestone.tasks.exists():
        return None

    if milestone.tasks.exclude(status__in=TERMINAL_STATUSES).exists():
        return None

    milestone.status = "completed"
    milestone.save(update_fields=["status", "updated_at"])
    return milestone


def maybe_reactivate_milestone(task):
    """Reactivate a completed milestone when one of its tasks is force-reset
    back to a non-terminal status.

    Mirror of `maybe_complete_milestone`. Without this, force-resetting a
    task into a completed milestone leaves the task in (e.g.) 'todo' but
    invisible to the claimable filter — a silent fail. This is admin-only
    territory (the reset endpoint is admin force-transition), so the
    implicit milestone state change is acceptable.

    Returns the milestone if it was reactivated, None otherwise.
    """
    milestone = getattr(task, "milestone", None)
    if milestone is None:
        return None

    if milestone.status != "completed":
        return None

    if task.status in TERMINAL_STATUSES:
        return None

    milestone.status = "active"
    milestone.save(update_fields=["status", "updated_at"])
    return milestone
