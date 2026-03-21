from django.db import models

from core.mixins import NanoIDMixin, TimestampMixin


class Workplan(NanoIDMixin, TimestampMixin):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="workplans",
    )
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


MILESTONE_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("active", "Active"),
    ("completed", "Completed"),
]


class Milestone(NanoIDMixin, TimestampMixin):
    STATUS_CHOICES = MILESTONE_STATUS_CHOICES

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    workplan = models.ForeignKey(
        Workplan,
        on_delete=models.CASCADE,
        related_name="milestones",
    )
    status = models.CharField(
        max_length=20,
        choices=MILESTONE_STATUS_CHOICES,
        default="pending",
    )
    order = models.IntegerField(default=0)
    default_needs_review_before_start = models.BooleanField(null=True, blank=True, default=None)
    default_needs_review_on_completion = models.BooleanField(null=True, blank=True, default=None)
    created_by = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return self.name


# Temporary alias for backwards compatibility - will be removed in task 8.3
Phase = Milestone