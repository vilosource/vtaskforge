from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """User-specific preferences and settings. One-to-one with User."""

    USER_TYPES = [
        ("human", "Human"),
        ("agent", "Agent"),
        ("service", "Service Account"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="human")
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


class ExternalIdentity(models.Model):
    """Maps external channel identities (Slack, WhatsApp, etc.) to vtf users."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="external_identities"
    )
    provider = models.CharField(max_length=30)
    external_id = models.CharField(max_length=255)
    workspace_id = models.CharField(max_length=255, blank=True, default="")
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_id", "workspace_id"],
                name="unique_external_identity",
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.external_id}"


class SessionRecord(models.Model):
    """Lightweight index of agent sessions. Points to cxdb for full traces."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_records"
    )
    project_id = models.CharField(max_length=50)
    role = models.CharField(max_length=30)
    # Pi/harness session ID — links a SessionRecord row to JSONL files on the
    # bridge's PVC for Phase 9 history attribution. Indexed but not unique:
    # multiple SessionRecords for the same Pi session are tolerated (e.g.,
    # acquire-then-release double-write).
    session_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    cxdb_context_id = models.IntegerField(null=True, blank=True)
    channel = models.CharField(max_length=30, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["project_id", "-started_at"]),
        ]

    def __str__(self):
        return f"{self.role}@{self.project_id}"


class AgentLock(models.Model):
    """Persistent agent session lock. One lock per project per role."""

    project_id = models.CharField(max_length=50)
    role = models.CharField(max_length=30)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_locks"
    )
    session_id = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project_id", "role"],
                name="unique_project_role_lock",
            ),
        ]

    def __str__(self):
        return f"Lock({self.role}@{self.project_id})"


class ChannelProjectMapping(models.Model):
    """Maps external channels (Slack, etc.) to projects."""

    provider = models.CharField(max_length=30)
    channel_id = models.CharField(max_length=255)
    channel_name = models.CharField(max_length=255, blank=True, default="")
    project_id = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "channel_id"],
                name="unique_channel_mapping",
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.channel_id} → {self.project_id}"


class ProjectMembership(models.Model):
    """Links users to projects with roles. Advisory until Phase 6."""

    ROLES = [
        ("owner", "Owner"),
        ("member", "Member"),
        ("viewer", "Viewer"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships"
    )
    project_id = models.CharField(max_length=50)
    role = models.CharField(max_length=20, choices=ROLES, default="member")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project_id"],
                name="unique_user_project",
            ),
        ]

    def __str__(self):
        return f"{self.user}:{self.project_id}({self.role})"
