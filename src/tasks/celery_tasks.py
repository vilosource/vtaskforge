"""
Celery periodic tasks for the tasks app.
"""
from celery import shared_task
from django.utils import timezone

from events.services import record_event
from tasks.models import Task
from tasks.state_machine import perform_transition


@shared_task
def expire_stale_claims():
    """
    Find tasks in 'doing' status with expired claims and move them to
    'needs_attention', clearing all claim fields and recording a TaskEvent.

    Returns the count of tasks that were expired.
    """
    now = timezone.now()
    expired_tasks = Task.objects.filter(
        status="doing",
        claim_expires_at__lt=now,
    )

    count = 0
    for task in expired_tasks:
        previous_agent = task.claimed_by.username if task.claimed_by else None

        # Clear claim fields separately from the status transition
        task.claimed_by = None
        task.claimed_at = None
        task.claim_expires_at = None
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at"])

        # Use state machine for status transition
        perform_transition(task, "needs_attention", trigger_source="system")

        # Record the claim_expired event via EventService
        record_event(task, "claim_expired", data={"previous_agent": previous_agent}, trigger_source="system")
        count += 1

    return count


@shared_task
def expire_stale_reviews():
    """R3 (I2 backstop for vafi#18): escalate tasks stuck in
    'pending_completion_review' past their review lease to
    'needs_attention' (the human terminal), recording a 'review_expired'
    TaskEvent. Sibling of expire_stale_claims — the system never rests
    in a silent non-terminal state, enforced server-side independent of
    the controller. See docs/review-phase-lease-DESIGN.md.

    Returns the count of reviews escalated.
    """
    now = timezone.now()
    stale = Task.objects.filter(
        status="pending_completion_review",
        review_expires_at__lt=now,
    )

    count = 0
    for task in stale:
        task.review_expires_at = None
        task.save(update_fields=["review_expires_at"])
        perform_transition(task, "needs_attention", trigger_source="system")
        record_event(task, "review_expired", data={}, trigger_source="system")
        count += 1

    return count


@shared_task
def expire_stale_integrations():
    """WC-1/C4 (I2 at DAG granularity): escalate tasks stuck in
    'integrating' past their integration lease to 'needs_attention',
    recording an 'integration_expired' TaskEvent. Closes the silent
    non-terminal that the C3 merge slot introduces (a controller that
    dies mid-merge would otherwise hold the milestone slot forever).
    Sibling of expire_stale_claims / expire_stale_reviews — no
    cross-talk: it filters strictly on status='integrating'.

    Returns the count of integrations escalated.
    """
    now = timezone.now()
    stale = Task.objects.filter(
        status="integrating",
        integration_expires_at__lt=now,
    )

    count = 0
    for task in stale:
        task.integration_expires_at = None
        task.save(update_fields=["integration_expires_at"])
        perform_transition(task, "needs_attention", trigger_source="system")
        record_event(task, "integration_expired", data={},
                     trigger_source="system")
        count += 1

    return count
