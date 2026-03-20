"""
Celery periodic tasks for the tasks app.
"""
from celery import shared_task
from django.utils import timezone

from events.models import TaskEvent
from tasks.models import Task


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
        previous_agent = task.claimed_by

        task.status = "needs_attention"
        task.claimed_by = None
        task.claimed_at = None
        task.claim_expires_at = None
        task.save(update_fields=["status", "claimed_by", "claimed_at", "claim_expires_at"])

        TaskEvent.objects.create(
            task=task,
            event_type="claim_expired",
            data={"previous_agent": previous_agent},
            triggered_by="system",
        )
        count += 1

    return count
