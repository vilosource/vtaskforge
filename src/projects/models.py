import re

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models

from core.mixins import NanoIDMixin, ProjectScopedModel, TimestampMixin

# RFC 1123 *label* (≤63): lowercase alphanumerics + internal hyphens, no
# leading/trailing hyphen. This is the contract for the project slug, which
# becomes the Vault path segment and the per-project K8s ServiceAccount suffix
# (`vtaskforge-executor-<slug>`). See docs/design/vtaskforge-variables-C2-PLAN.md §Q1.
SLUG_REGEX = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
slug_validator = RegexValidator(
    regex=SLUG_REGEX,
    message=(
        "Must be a lowercase RFC 1123 label: a-z, 0-9 and internal hyphens "
        "only, no leading/trailing hyphen."
    ),
)


def derive_slug(name: str) -> str:
    """Slugify a display name into an RFC 1123 label (may be empty)."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower())
    return s.strip("-")[:63].rstrip("-")


class Project(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "id"
    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    # Immutable, K8s-safe operational identity (distinct from the opaque nanoid
    # PK). Auto-derived from `name` on create; the Vault path segment + future
    # per-project SA suffix. null while the backfill migration runs; enforced
    # NOT NULL afterwards.
    slug = models.CharField(
        max_length=63,
        unique=True,
        blank=True,
        validators=[slug_validator],
    )
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

    def save(self, *args, **kwargs):
        # Derive the slug once, on insert. It is immutable thereafter (the API
        # layer rejects changes); a rename of `name` never touches the slug.
        if self._state.adding and not self.slug:
            self.slug = self._unique_slug(derive_slug(self.name) or "project")
        super().save(*args, **kwargs)

    def _unique_slug(self, base: str) -> str:
        base = (base[:63].rstrip("-")) or "project"
        candidate, n = base, 2
        while Project.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            suffix = f"-{n}"
            candidate = f"{base[:63 - len(suffix)].rstrip('-')}{suffix}"
            n += 1
        return candidate

    def get_project_id(self) -> str | None:
        return self.id

    def __str__(self):
        return self.name
