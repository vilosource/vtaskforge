from django.db import models

from core.mixins import NanoIDMixin

EVENT_TYPE_CHOICES = [
    ("status_changed", "Status Changed"),
    ("claimed", "Claimed"),
    ("unclaimed", "Unclaimed"),
    ("claim_expired", "Claim Expired"),
    ("review_submitted", "Review Submitted"),
    ("link_added", "Link Added"),
    ("link_removed", "Link Removed"),
    ("field_updated", "Field Updated"),
    ("force_transition", "Force Transition"),
]


class TaskEvent(NanoIDMixin):
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    data = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    triggered_by = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.event_type} on {self.task_id} at {self.timestamp}"
