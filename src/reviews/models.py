from django.contrib.auth.models import User
from django.db import models

from core.mixins import NanoIDMixin, TimestampMixin

DECISION_CHOICES = [
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("changes_requested", "Changes Requested"),
]

REVIEWER_TYPE_CHOICES = [
    ("human", "Human"),
    ("agent", "Agent"),
]


class Review(NanoIDMixin, TimestampMixin):
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    reason = models.TextField(blank=True, default="")
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviews",
    )
    reviewer_type = models.CharField(
        max_length=10,
        choices=REVIEWER_TYPE_CHOICES,
        default="human",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        reviewer_name = self.reviewer.username if self.reviewer else "unknown"
        return f"{self.decision} by {reviewer_name} on {self.task_id}"
