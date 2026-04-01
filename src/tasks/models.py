from django.db import models

from core.mixins import NanoIDMixin, TimestampMixin

TASK_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("pending_start_review", "Pending Start Review"),
    ("todo", "To Do"),
    ("doing", "Doing"),
    ("pending_completion_review", "Pending Completion Review"),
    ("changes_requested", "Changes Requested"),
    ("needs_attention", "Needs Attention"),
    ("blocked", "Blocked"),
    ("deferred", "Deferred"),
    ("cancelled", "Cancelled"),
    ("done", "Done"),
]


class Task(NanoIDMixin, TimestampMixin):
    STATUS_CHOICES = TASK_STATUS_CHOICES

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=30,
        choices=TASK_STATUS_CHOICES,
        default="draft",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    milestone = models.ForeignKey(
        "workplans.Milestone",
        on_delete=models.CASCADE,
        related_name="tasks",
        null=True,
        blank=True,
        default=None,
    )
    workplan = models.ForeignKey(
        "workplans.Workplan",
        on_delete=models.CASCADE,
        related_name="tasks",
        null=True,
        blank=True,
        default=None,
    )
    acceptance_criteria = models.JSONField(default=list, blank=True)
    labels = models.JSONField(default=list, blank=True)
    needs_review_before_start = models.BooleanField(null=True, blank=True, default=None)
    needs_review_on_completion = models.BooleanField(null=True, blank=True, default=True)
    review_return_to = models.CharField(max_length=30, null=True, blank=True, default=None)
    requires = models.JSONField(default=list, blank=True)
    assigned_to = models.CharField(max_length=255, null=True, blank=True, default=None)
    claimed_by = models.CharField(max_length=255, null=True, blank=True, default=None)
    claimed_at = models.DateTimeField(null=True, blank=True, default=None)
    claim_timeout = models.DurationField(null=True, blank=True, default=None)
    claim_expires_at = models.DateTimeField(null=True, blank=True, default=None)
    created_by = models.CharField(max_length=255, blank=True, default="")
    spec = models.TextField(blank=True, default="")
    agent_model = models.CharField(max_length=30, blank=True, default="")
    test_command = models.JSONField(default=dict, blank=True)
    judge = models.BooleanField(default=False)
    isolation = models.CharField(max_length=20, blank=True, default="sequential")
    retry_count = models.IntegerField(default=0)
    execution_summary = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.title


class Note(NanoIDMixin):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="notes")
    text = models.TextField()
    actor_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.text[:50]
