from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from events.services import record_event
from tasks.exceptions import GuardViolation, InvalidTransition

# R3: review-phase lease. A task entering pending_completion_review
# gets a deadline; expire_stale_reviews escalates it to needs_attention
# if no verdict is recorded in time (the I2 backstop for vafi#18).
DEFAULT_REVIEW_TIMEOUT_MINUTES = 30

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
        "needs_attention",       # R3: review lease expired / verdict
                                 # unrecordable → escalate to the human
                                 # terminal (I2 backstop; reaper-driven).
                                 # See docs/review-phase-lease-DESIGN.md
    ],
    "changes_requested": [
        "doing",                     # executor reclaims for rework (vafi)
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


# ---------------------------------------------------------------------------
# Guards — task-level invariant checks for transitions
# ---------------------------------------------------------------------------

def guard_has_workplan(task):
    """Task must belong to a workplan before entering todo."""
    if task.workplan is None:
        raise GuardViolation(
            task.status, "todo",
            guard_name="guard_has_workplan",
            message="Cannot move task to todo: task must belong to a workplan. "
                    "Add the task to a workplan first.",
        )


def guard_milestone_active(task):
    """If task has a milestone, it must be active to leave draft."""
    if task.milestone and task.milestone.status != "active":
        raise GuardViolation(
            task.status, "todo",
            guard_name="guard_milestone_active",
            message=f"Cannot transition task: milestone '{task.milestone.name}' "
                    f"is '{task.milestone.status}', not 'active'.",
        )


# Guards keyed by when they fire:
# ENTRY_GUARDS[status] — fires on ANY transition INTO that status
# EXIT_GUARDS[status] — fires on ANY transition FROM that status

ENTRY_GUARDS = {
    "todo": [guard_has_workplan],
}

EXIT_GUARDS = {
    "draft": [guard_milestone_active],
}


def _run_guards(task, old_status, new_status):
    """Run all applicable guards for a transition."""
    for guard in EXIT_GUARDS.get(old_status, []):
        guard(task)
    for guard in ENTRY_GUARDS.get(new_status, []):
        guard(task)


# ---------------------------------------------------------------------------
# Core state machine
# ---------------------------------------------------------------------------

def get_valid_transitions(current_status: str) -> list[str]:
    return VALID_TRANSITIONS.get(current_status, [])


def validate_transition(task, new_status: str) -> None:
    valid = get_valid_transitions(task.status)
    if new_status not in valid:
        raise InvalidTransition(task.status, new_status, valid)


def perform_transition(task, new_status: str, trigger_source: str = "", actor=None):
    validate_transition(task, new_status)
    _run_guards(task, task.status, new_status)
    old_status = task.status
    task.status = new_status
    _fields = ["status", "updated_at"]
    if new_status == "pending_completion_review":
        mins = getattr(settings, "REVIEW_TIMEOUT_MINUTES",
                       DEFAULT_REVIEW_TIMEOUT_MINUTES)
        task.review_expires_at = timezone.now() + timedelta(minutes=mins)
        _fields.append("review_expires_at")
    task.save(update_fields=_fields)
    record_event(task, "status_changed", data={"from": old_status, "to": new_status},
                 trigger_source=trigger_source, actor=actor)

    if new_status in TERMINAL_STATUSES:
        try:
            from workplans.completion import maybe_complete_milestone
            maybe_complete_milestone(task)
        except Exception:
            pass  # don't break transitions if milestone completion fails

    return task
