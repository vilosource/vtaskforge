from django.contrib.auth.models import User
from django.db import models

from core.mixins import NanoIDMixin, ProjectScopedModel, TimestampMixin


class Workplan(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "project_id"
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
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_workplans",
    )
    tags = models.JSONField(default=list, blank=True)
    target_date = models.DateTimeField(null=True, blank=True)
    default_needs_review_before_start = models.BooleanField(default=False)
    default_needs_review_on_completion = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_workplans",
    )

    class Meta:
        ordering = ["-created_at"]

    def get_project_id(self) -> str | None:
        return self.project_id

    def __str__(self):
        return self.name


MILESTONE_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("active", "Active"),
    ("completed", "Completed"),
]


class Milestone(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "workplan__project_id"
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
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_milestones",
    )

    class Meta:
        ordering = ["order", "created_at"]

    def get_project_id(self) -> str | None:
        return self.workplan.project_id if self.workplan_id else None

    def __str__(self):
        return self.name


# Temporary alias for backwards compatibility - will be removed in task 8.3
Phase = Milestone