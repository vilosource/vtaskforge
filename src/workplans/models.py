from django.db import models

from core.mixins import NanoIDMixin, TimestampMixin


class Workplan(NanoIDMixin, TimestampMixin):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    owner = models.CharField(max_length=255, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    target_date = models.DateTimeField(null=True, blank=True)
    default_needs_review_before_start = models.BooleanField(default=False)
    default_needs_review_on_completion = models.BooleanField(default=False)
    created_by = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
