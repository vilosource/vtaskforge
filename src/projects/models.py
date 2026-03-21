from django.db import models

from core.mixins import NanoIDMixin, TimestampMixin


class Project(NanoIDMixin, TimestampMixin):
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
    owner = models.CharField(max_length=255, blank=True, default="")
    created_by = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name