import re
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
    "pending_completion_review", "integrating", "changes_requested",
    "needs_attention", "blocked", "deferred"
}

# WC-1/C4: workgraph integration lease (minutes). Set on entry to
# 'integrating'; expire_stale_integrations reaps past this.
DEFAULT_INTEGRATION_TIMEOUT_MINUTES = 30

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
        "done",                  # approved (non-workgraph — V16 unchanged)
        "integrating",           # WC-1/C3: approved workgraph task takes
                                 # the milestone merge slot
        "changes_requested",     # rejected
        "cancelled",
        "deferred",
        "needs_attention",       # R3: review lease expired / verdict
                                 # unrecordable → escalate to the human
                                 # terminal (I2 backstop; reaper-driven).
                                 # See docs/review-phase-lease-DESIGN.md
    ],
    "integrating": [             # WC-1/C3: serialized merge point
        "done",                  # controller reports merge success
        "needs_attention",       # conflict (I2) or integration lease
                                 # expired → bounded rework
        "cancelled",
        "deferred",
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

def guard_done_via_integration(task):
    """WC-1/C3 (I4): a workgraph task (its milestone owns an integration
    branch) may only reach 'done' through a recorded successful
    integration — i.e. from 'integrating'. Non-workgraph tasks are
    unaffected (V16 — straight pending_completion_review → done)."""
    is_workgraph = bool(
        task.milestone_id and task.milestone.integration_branch
    )
    if is_workgraph and task.status != "integrating":
        raise GuardViolation(
            task.status, "done",
            guard_name="guard_done_via_integration",
            message="Workgraph task cannot reach 'done' directly: it must "
                    "pass through 'integrating' (a recorded successful "
                    f"merge into '{task.milestone.integration_branch}').",
        )


# R6 (MQ-F3): the canonical fail-loud directive clause (spec-author
# bugfix.md R3 / verifier V7). Distinctive enough to match deterministically
# regardless of surrounding wording; compared lower-cased.
FAIL_LOUD_SIGNATURE = "do not rationalize partial completion as success"


def guard_spec_admissible(task):
    """R6 spec-admission gate — the recursive image of the delivery gate.

    A spec is admissible to ``todo`` (the claimable state) only if its
    machine-checkable claims are actually gated. Enforces the deterministic,
    field-local floor (semantic checks remain the verifier-agent's job; see
    docs/r6-spec-admission-gate-DESIGN.md):

    - **A1 — F2 AC-id coverage:** AC ids are 1-based positional (the Nth
      acceptance_criteria item is ``AC<N>``); every id must appear as a
      labelled assertion in ``test_command.command``. An uncovered AC is
      decorative ⇒ inadmissible.
    - **A2 — non-empty gate:** a task with ACs but no ``test_command`` has
      no machine gate.
    - **A3 — fail-loud directive present** in the spec body.

    Tasks with **no** acceptance_criteria are exempt (OQ-R6a): they are not
    SDD specs, and the always-present delivery gate already backstops them
    against ghost-completion (F7/F10).
    """
    acs = task.acceptance_criteria or []
    if not acs:
        return
    command = ((task.test_command or {}).get("command") or "")
    if not command.strip():
        raise GuardViolation(
            task.status, "todo",
            guard_name="guard_spec_admissible",
            message="Spec inadmissible: has acceptance_criteria but empty "
                    "test_command (no machine gate). [A2]",
        )
    # Word-boundary match, not substring containment: 'AC1' is a substring of
    # 'AC10'..'AC19', so plain `in` would falsely count single-digit ids as
    # covered for specs with >=10 ACs — re-opening the decorative-AC hole.
    uncovered = [f"AC{i}" for i in range(1, len(acs) + 1)
                 if not re.search(rf"\bAC{i}\b", command)]
    if uncovered:
        raise GuardViolation(
            task.status, "todo",
            guard_name="guard_spec_admissible",
            message=f"Spec inadmissible: acceptance criteria with no "
                    f"AC-id-labelled gate assertion: {uncovered}. Every AC "
                    f"needs >=1 labelled assertion in test_command (F2). [A1]",
        )
    if FAIL_LOUD_SIGNATURE not in (task.spec or "").lower():
        raise GuardViolation(
            task.status, "todo",
            guard_name="guard_spec_admissible",
            message="Spec inadmissible: missing fail-loud directive in the "
                    "spec body (V7/R3). [A3]",
        )


ENTRY_GUARDS = {
    "todo": [guard_has_workplan, guard_spec_admissible],
    "done": [guard_done_via_integration],
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
    if new_status == "integrating":
        mins = getattr(settings, "INTEGRATION_TIMEOUT_MINUTES",
                       DEFAULT_INTEGRATION_TIMEOUT_MINUTES)
        task.integration_expires_at = timezone.now() + timedelta(minutes=mins)
        _fields.append("integration_expires_at")
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
