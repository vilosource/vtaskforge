from django.db import models

from core.mixins import NanoIDMixin, TimestampMixin

LINK_TYPE_CHOICES = [
    ("depends_on", "Depends On"),
    ("blocks", "Blocks"),
    ("relates_to", "Relates To"),
    ("commit", "Commit"),
    ("mr", "Merge Request"),
    ("area", "KB Area"),
    ("doc", "Document"),
    ("file", "File"),
    ("jira", "Jira"),
]

SOURCE_TYPE_CHOICES = [
    ("workplan", "Workplan"),
    ("phase", "Phase"),
    ("task", "Task"),
]


class Link(NanoIDMixin, TimestampMixin):
    LINK_TYPE_CHOICES = LINK_TYPE_CHOICES
    SOURCE_TYPE_CHOICES = SOURCE_TYPE_CHOICES

    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    source_id = models.CharField(max_length=21)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=255)
    link_type = models.CharField(max_length=20, choices=LINK_TYPE_CHOICES)
    metadata = models.JSONField(null=True, blank=True, default=None)
    created_by = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["source_type", "source_id"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"{self.source_type}:{self.source_id} --[{self.link_type}]--> {self.target_type}:{self.target_id}"
