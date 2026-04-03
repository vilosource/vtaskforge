from django.db import models
from nanoid import generate


def generate_nanoid():
    """Generate a 21-character nanoid string.

    Module-level callable so Django can serialize it in migrations.
    """
    return generate(size=21)


class ProjectScopedModel:
    """Protocol for models that belong to a project."""

    project_filter_path: str = "project_id"

    def get_project_id(self) -> str | None:
        raise NotImplementedError


class NanoIDMixin(models.Model):
    id = models.CharField(
        max_length=21,
        primary_key=True,
        default=generate_nanoid,
        editable=False,
    )

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
