"""Convert Project identity fields from CharField to FK User.

Phase 0, Step 5: rename old columns, add FK columns, data migration, drop old columns.
"""

import logging

from django.db import migrations, models
import django.db.models.deletion

logger = logging.getLogger(__name__)


def resolve_identity_fields(apps, schema_editor):
    """Populate new FK columns from old string columns."""
    User = apps.get_model("auth", "User")

    user_map = {u.username: u.pk for u in User.objects.all()}

    stats = {"resolved": 0, "unresolvable": 0, "empty": 0}

    db_alias = schema_editor.connection.alias
    from django.db import connections
    cursor = connections[db_alias].cursor()

    cursor.execute("SELECT id, _old_owner, _old_created_by FROM projects_project")
    for row in cursor.fetchall():
        project_id, old_owner, old_created_by = row
        updates = {}

        for old_val, new_col in [(old_owner, "owner_id"),
                                  (old_created_by, "created_by_id")]:
            if not old_val or old_val.strip() == "":
                stats["empty"] += 1
                continue

            user_pk = user_map.get(old_val)
            if user_pk:
                updates[new_col] = user_pk
                stats["resolved"] += 1
            else:
                stats["unresolvable"] += 1
                logger.warning(f"Unresolvable identity '{old_val}' on project {project_id}")

        if updates:
            set_clause = ", ".join(f"{col} = %s" for col in updates.keys())
            cursor.execute(
                f"UPDATE projects_project SET {set_clause} WHERE id = %s",
                list(updates.values()) + [project_id],
            )

    logger.info(f"Project identity migration: {stats}")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("projects", "0001_initial"),
        ("auth", "__first__"),
    ]

    operations = [
        # 1. Rename old CharField columns
        migrations.RenameField(
            model_name="project",
            old_name="owner",
            new_name="_old_owner",
        ),
        migrations.RenameField(
            model_name="project",
            old_name="created_by",
            new_name="_old_created_by",
        ),

        # 2. Add new FK columns
        migrations.AddField(
            model_name="project",
            name="owner",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="owned_projects",
                to="auth.user",
            ),
        ),
        migrations.AddField(
            model_name="project",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_projects",
                to="auth.user",
            ),
        ),

        # 3. Data migration
        migrations.RunPython(resolve_identity_fields, reverse_noop),

        # 4. Drop old columns
        migrations.RemoveField(model_name="project", name="_old_owner"),
        migrations.RemoveField(model_name="project", name="_old_created_by"),
    ]
