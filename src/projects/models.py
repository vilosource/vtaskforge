from django.contrib.auth.models import User
from django.db import models

from core.mixins import NanoIDMixin, ProjectScopedModel, TimestampMixin


class Project(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "id"
    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )
    repo_url = models.CharField(max_length=500, blank=True, default="")
    default_branch = models.CharField(max_length=100, blank=True, default="main")
    tags = models.JSONField(default=list, blank=True)
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_projects",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_projects",
    )

    class Meta:
        ordering = ["-created_at"]

    def get_project_id(self) -> str | None:
        return self.id

    def __str__(self):
        return self.name