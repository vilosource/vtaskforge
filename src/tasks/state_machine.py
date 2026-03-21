from tasks.exceptions import InvalidTransition

TERMINAL_STATUSES = {"done", "cancelled"}

NON_TERMINAL_STATUSES = {
    "draft", "pending_start_review", "todo", "doing",
    "pending_completion_review", "changes_requested",
    "needs_attention", "blocked", "deferred"
}

VALID_TRANSITIONS = {
    "draft": [
        "pending_start_review",  # needs_review_before_start = true
        "todo",                  # needs_review_before_start = false
        "cancelled",
        "deferred",
    ],
    "pending_start_review": [
        "todo",                  # approved
        "changes_requested",     # rejected
        "cancelled",
        "deferred",
    ],
    "todo": [
        "doing",                 # claimed by agent
        "blocked",
        "cancelled",
        "deferred",
    ],
    "doing": [
        "todo",                       # unclaimed / released back to queue
        "pending_completion_review",  # needs_review_on_completion = true
        "done",                       # needs_review_on_completion = false
        "needs_attention",            # agent gave up
        "blocked",
        "cancelled",
        "deferred",
    ],
    "pending_completion_review": [
        "done",                  # approved
        "changes_requested",     # rejected
        "cancelled",
        "deferred",
    ],
    "changes_requested": [
        "pending_start_review",
        "pending_completion_review",
        "draft",                 # major rework
        "cancelled",
        "deferred",
    ],
    "needs_attention": [
        "draft",
        "todo",
        "cancelled",
        "deferred",
    ],
    "blocked": [
        "todo",
        "doing",
        "cancelled",
        "deferred",
    ],
    "deferred": [
        "todo",
        "cancelled",
    ],
    "cancelled": [],  # terminal
    "done": [],       # terminal
}


def get_valid_transitions(current_status: str) -> list[str]:
    return VALID_TRANSITIONS.get(current_status, [])


def validate_transition(task, new_status: str) -> None:
    valid = get_valid_transitions(task.status)
    if new_status not in valid:
        raise InvalidTransition(task.status, new_status, valid)


def perform_transition(task, new_status: str, triggered_by: str = ""):
    validate_transition(task, new_status)
    old_status = task.status
    task.status = new_status
    task.save(update_fields=["status", "updated_at"])
    try:
        from events.models import TaskEvent
        TaskEvent.objects.create(
            task=task,
            event_type="status_changed",
            data={"from": old_status, "to": new_status},
            triggered_by=triggered_by,
        )
    except Exception:
        pass  # don't break transitions if event creation fails

    if new_status in TERMINAL_STATUSES:
        try:
            from workplans.completion import maybe_complete_phase
            maybe_complete_phase(task)
        except Exception:
            pass  # don't break transitions if phase completion fails

    return task
