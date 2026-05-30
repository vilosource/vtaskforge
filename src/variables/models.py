"""vtaskforge variables substrate — C.2 (schema + admission).

`ProjectVariable` is the per-project *declaration* of a secret variable. The
*value* never lives here — it lives in Vault (read by the vafi controller at
spawn time, C.3). `VariableAudit` is the forensic record of each fetch attempt.

See viloforge-platform/docs/vtaskforge-variables-DESIGN.md §"Data model" and
docs/design/vtaskforge-variables-C2-PLAN.md.
"""
import uuid

from django.db import models

from core.mixins import NanoIDMixin, ProjectScopedModel, TimestampMixin

ROLE_CHOICES = [
    ("executor", "Executor"),
    ("judge", "Judge"),
]

SCOPE_CHOICES = [
    ("project", "Project"),
    ("shared", "Shared"),
]

AUDIT_RESULT_CHOICES = [
    ("success", "Success"),
    ("not_found", "Not Found"),
    ("empty", "Empty"),
    ("unreachable", "Unreachable"),
    ("permission_denied", "Permission Denied"),
]


class ProjectVariable(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    """A per-project secret-variable declaration.

    `name` is the *logical* name task specs reference; it also becomes the
    trailing Vault path segment and the default env binding. `role`
    discriminates executor vs judge access — the same `name` may exist for both
    roles independently. The surrogate NanoID PK + the `(project, name, role)`
    uniqueness together express the design's composite key while keeping DRF
    detail routes single-column.
    """

    project_filter_path = "project_id"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="variables",
    )
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default="project")
    description = models.TextField(null=True, blank=True)
    required = models.BooleanField(default=True)

    class Meta:
        unique_together = (("project", "name", "role"),)
        ordering = ["name", "role"]

    def get_project_id(self) -> str | None:
        return self.project_id

    def __str__(self) -> str:
        return f"{self.project_id}/{self.role}/{self.name}"


class VariableAudit(ProjectScopedModel, TimestampMixin):
    """Forensic record of one controller fetch attempt at spawn time.

    NEVER stores the value, a hash of the value, or a prefix of the value —
    only metadata for grep + a Vault-audit join (design §"Audit-log integrity").
    UUID PK (not NanoID) because rows are written by multiple controller
    replicas without coordination.
    """

    project_filter_path = "project_id"

    audit_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField()  # controller wall clock (UTC)
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variable_audits",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variable_audits",
    )
    variable_name = models.CharField(max_length=255)
    variable_scope = models.CharField(max_length=16, choices=SCOPE_CHOICES)
    vault_path = models.TextField()
    vault_version = models.IntegerField(null=True, blank=True)
    result = models.CharField(max_length=20, choices=AUDIT_RESULT_CHOICES)
    size_bytes = models.IntegerField(null=True, blank=True)
    duration_ms = models.IntegerField()
    controller_id = models.CharField(max_length=255)

    class Meta:
        ordering = ["-timestamp"]

    def get_project_id(self) -> str | None:
        return self.project_id

    def __str__(self) -> str:
        return f"{self.variable_name}@{self.timestamp.isoformat()} → {self.result}"
