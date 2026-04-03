from events.services import record_event
from tasks.exceptions import InvalidTransition
from tasks.models import Task
from tasks.state_machine import perform_transition

from .models import Review

REVIEW_STATUSES = {"pending_start_review", "pending_completion_review"}


class ReviewError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def submit_review(
    task_id: str,
    decision: str,
    reason: str = "",
    reviewer=None,
    reviewer_type: str = "human",
) -> dict:
    """
    Submit a review for a task.

    decision must be one of: "approved", "changes_requested", "rejected"

    Validates the task is in a review status, routes state transitions based on
    decision and current status, creates a Review record, and records an event.

    Returns: {'review': Review, 'task': Task, 'previous_status': str}
    Raises ReviewError if the task is not in a review status.
    """
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        raise ReviewError(f"Task '{task_id}' not found.", status_code=404)

    if task.status not in REVIEW_STATUSES:
        raise ReviewError(
            f"Reviews can only be submitted when task is in a review state. "
            f"Current status: '{task.status}'.",
            status_code=400,
        )

    previous_status = task.status

    if decision == "approved":
        if task.status == "pending_start_review":
            perform_transition(task, "todo")
        else:  # pending_completion_review
            perform_transition(task, "done")
    else:
        # rejected or changes_requested — set review_return_to BEFORE transitioning
        task.review_return_to = task.status
        task.save(update_fields=["review_return_to", "updated_at"])
        perform_transition(task, "changes_requested")

    review = Review.objects.create(
        task=task,
        decision=decision,
        reason=reason,
        reviewer=reviewer,
        reviewer_type=reviewer_type,
    )

    reviewer_name = reviewer.username if reviewer else ""
    record_event(
        task,
        "review_submitted",
        data={
            "decision": decision,
            "reviewer_id": reviewer_name,
            "reviewer_type": reviewer_type,
            "previous_status": previous_status,
        },
        trigger_source="review",
        actor=reviewer,
    )

    return {"review": review, "task": task, "previous_status": previous_status}
