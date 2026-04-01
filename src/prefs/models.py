from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """User-specific preferences and settings. One-to-one with User."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"


class RecentAccess(models.Model):
    """Tracks the most recent resources accessed by a user."""

    RESOURCE_TYPES = [
        ("project", "Project"),
        ("workplan", "Workplan"),
        ("task", "Task"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recent_accesses"
    )
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    resource_id = models.CharField(max_length=50)
    resource_title = models.CharField(max_length=255)
    resource_status = models.CharField(max_length=30, blank=True, default="")
    accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-accessed_at"]
        indexes = [
            models.Index(fields=["user", "-accessed_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "resource_type", "resource_id"],
                name="unique_user_resource_access",
            ),
        ]

    def __str__(self):
        return f"{self.resource_type}:{self.resource_id}"
