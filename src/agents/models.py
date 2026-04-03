from django.contrib.auth.models import User
from django.db import models

from core.mixins import NanoIDMixin, TimestampMixin


class Agent(NanoIDMixin, TimestampMixin):
    STATUS_CHOICES = [
        ("online", "Online"),
        ("offline", "Offline"),
        ("busy", "Busy"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="agent",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="offline",
    )
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    pod_name = models.CharField(max_length=255, null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self):
        return self.name
