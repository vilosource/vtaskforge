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
    reviewer_id = models.CharField(max_length=255)
    reviewer_type = models.CharField(
        max_length=10,
        choices=REVIEWER_TYPE_CHOICES,
        default="human",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.decision} by {self.reviewer_id} on {self.task_id}"
