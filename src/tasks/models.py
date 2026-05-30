from django.contrib.auth.models import User
from django.db import models

from core.mixins import NanoIDMixin, ProjectScopedModel, TimestampMixin

TASK_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("pending_start_review", "Pending Start Review"),
    ("todo", "To Do"),
    ("doing", "Doing"),
    ("pending_completion_review", "Pending Completion Review"),
    ("integrating", "Integrating"),
    ("changes_requested", "Changes Requested"),
    ("needs_attention", "Needs Attention"),
    ("blocked", "Blocked"),
    ("deferred", "Deferred"),
    ("cancelled", "Cancelled"),
    ("done", "Done"),
]


class Task(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "project_id"
    STATUS_CHOICES = TASK_STATUS_CHOICES

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default="")
    # Declared secret-variable references for this task (the `variables:` spec
    # field). Validated at admission (variables.admission.validate_task_variables)
    # and consumed by the vafi controller at spawn (C.3). Defaults to [] — tasks
    # without variables are unaffected.
    variables = models.JSONField(default=list, blank=True)
    # Snapshot of { variable_name: vault_version } captured at spawn time by the
    # vafi controller (populated in C.3); enables forensic replay. Nullable —
    # tasks without a `variables:` block leave it None. See variables substrate.
    secrets_snapshot = models.JSONField(null=True, blank=True)
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
    # `requires` historically was overloaded: callers stored bare capability
    # tag strings ("executor", "pi") AND task dependency ref dicts.
    # find_claimable_tasks treated it as the former; the SDK typed it as
    # list[TaskRef]. Migration 0014 splits them: bare strings move to
    # `required_tags`; dep refs stay in `requires`.
    requires = models.JSONField(default=list, blank=True)
    required_tags = models.JSONField(default=list, blank=True)
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_tasks",
    )
    claimed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="claimed_tasks",
    )
    claimed_at = models.DateTimeField(null=True, blank=True, default=None)
    claim_timeout = models.DurationField(null=True, blank=True, default=None)
    claim_expires_at = models.DateTimeField(null=True, blank=True, default=None)
    # R3: review-phase lease — set on entry to pending_completion_review;
    # expire_stale_reviews escalates to needs_attention if exceeded.
    review_expires_at = models.DateTimeField(null=True, blank=True, default=None)
    # WC-1/C4: workgraph integration lease — set on entry to 'integrating';
    # expire_stale_integrations escalates to needs_attention if exceeded
    # (I2 at DAG granularity; closes the silent non-terminal C3 introduces).
    integration_expires_at = models.DateTimeField(null=True, blank=True, default=None)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_tasks",
    )
    spec = models.TextField(blank=True, default="")
    agent_model = models.CharField(max_length=30, blank=True, default="")
    test_command = models.JSONField(default=dict, blank=True)
    judge = models.BooleanField(default=False)
    isolation = models.CharField(max_length=20, blank=True, default="sequential")
    retry_count = models.IntegerField(default=0)
    execution_summary = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        ordering = ["created_at"]

    def get_project_id(self) -> str | None:
        return self.project_id

    def __str__(self):
        return self.title


class Note(ProjectScopedModel, NanoIDMixin):
    project_filter_path = "task__project_id"
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="notes")
    text = models.TextField()
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="task_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def get_project_id(self) -> str | None:
        return self.task.project_id if self.task_id else None

    def __str__(self):
        return self.text[:50]
