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
