"""Core models — cross-cutting concerns."""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class ConsoleAuthCodeManager(models.Manager):
    def create_code(self, user, redirect_uri, ttl_seconds=60):
        """Create a single-use authorization code for vafi-console."""
        code = secrets.token_hex(32)
        expires_at = timezone.now() + timezone.timedelta(seconds=ttl_seconds)
        return self.create(
            code=code,
            user=user,
            redirect_uri=redirect_uri,
            expires_at=expires_at,
        )

    def validate_code(self, code):
        """Validate and consume a code. Returns the code object or None."""
        try:
            auth_code = self.select_related("user").get(
                code=code,
                used=False,
                expires_at__gt=timezone.now(),
            )
        except self.model.DoesNotExist:
            return None
        auth_code.used = True
        auth_code.save(update_fields=["used"])
        return auth_code


class ConsoleAuthCode(models.Model):
    """Single-use authorization code for vafi-console authentication.

    Flow: vtf generates code → console exchanges code for user info.
    Codes expire after 60 seconds and can only be used once.
    """

    code = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="console_auth_codes",
    )
    redirect_uri = models.URLField(max_length=500)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ConsoleAuthCodeManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ConsoleAuthCode({self.code[:8]}... user={self.user.username})"
