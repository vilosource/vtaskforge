import re

from django.db import migrations


def backfill_slugs(apps, schema_editor):
    """Derive a unique RFC 1123 slug for every existing project.

    Self-contained (historical model has no custom save()/derive_slug). Free of
    secret relocation — the variables substrate is greenfield, so no Vault paths
    are keyed on these projects yet.
    """
    Project = apps.get_model("projects", "Project")
    used = set(
        Project.objects.exclude(slug__isnull=True).values_list("slug", flat=True)
    )
    for p in Project.objects.filter(slug__isnull=True).order_by("created_at", "id"):
        base = re.sub(r"[^a-z0-9]+", "-", (p.name or "").lower()).strip("-")[:63].rstrip("-") or "project"
        candidate, n = base, 2
        while candidate in used:
            suffix = f"-{n}"
            candidate = f"{base[:63 - len(suffix)].rstrip('-')}{suffix}"
            n += 1
        p.slug = candidate
        p.save(update_fields=["slug"])
        used.add(candidate)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0003_add_project_slug"),
    ]

    operations = [
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
    ]
