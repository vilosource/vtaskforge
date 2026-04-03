"""Convert Link.created_by from CharField to FK User, add Link.project denormalization.

Phase 0, Step 6: rename-add-resolve-drop for created_by, plus project backfill.
"""

import logging

from django.db import migrations, models
import django.db.models.deletion

logger = logging.getLogger(__name__)


def resolve_identity_and_backfill_project(apps, schema_editor):
    """Populate created_by FK from old string column, and backfill project from source entity."""
    User = apps.get_model("auth", "User")
    Task = apps.get_model("tasks", "Task")
    Workplan = apps.get_model("workplans", "Workplan")
    Milestone = apps.get_model("workplans", "Milestone")

    user_map = {u.username: u.pk for u in User.objects.all()}

    db_alias = schema_editor.connection.alias
    from django.db import connections
    cursor = connections[db_alias].cursor()

    # --- created_by resolution ---
    stats = {"resolved": 0, "unresolvable": 0, "empty": 0}
    cursor.execute("SELECT id, _old_created_by FROM links_link")
    for row in cursor.fetchall():
        link_id, old_created_by = row
        if not old_created_by or old_created_by.strip() == "":
            stats["empty"] += 1
            continue

        user_pk = user_map.get(old_created_by)
        if user_pk:
            cursor.execute(
                "UPDATE links_link SET created_by_id = %s WHERE id = %s",
                [user_pk, link_id],
            )
            stats["resolved"] += 1
        else:
            stats["unresolvable"] += 1
            logger.warning(f"Unresolvable identity '{old_created_by}' on link {link_id}")

    logger.info(f"Link identity migration: {stats}")

    # --- project backfill ---
    # Build lookup maps
    task_project_map = dict(
        Task.objects.filter(project__isnull=False).values_list("id", "project_id")
    )
    workplan_project_map = dict(
        Workplan.objects.filter(project__isnull=False).values_list("id", "project_id")
    )
    milestone_workplan_map = dict(
        Milestone.objects.values_list("id", "workplan_id")
    )

    stats = {"backfilled": 0, "not_found": 0}
    cursor.execute("SELECT id, source_type, source_id FROM links_link WHERE project_id IS NULL")
    for row in cursor.fetchall():
        link_id, source_type, source_id = row
        project_id = None

        if source_type == "task":
            project_id = task_project_map.get(source_id)
        elif source_type == "workplan":
            project_id = workplan_project_map.get(source_id)
        elif source_type == "milestone":
            workplan_id = milestone_workplan_map.get(source_id)
            if workplan_id:
                project_id = workplan_project_map.get(workplan_id)

        if project_id:
            cursor.execute(
                "UPDATE links_link SET project_id = %s WHERE id = %s",
                [project_id, link_id],
            )
            stats["backfilled"] += 1
        else:
            stats["not_found"] += 1

    logger.info(f"Link project backfill: {stats}")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("links", "0003_alter_link_source_type"),
        ("auth", "__first__"),
        ("projects", "0002_convert_identity_to_fk"),
        ("tasks", "0012_convert_identity_fields_to_fk"),
        ("workplans", "0008_convert_identity_to_fk"),
    ]

    operations = [
        # 1. Rename old created_by CharField
        migrations.RenameField(
            model_name="link",
            old_name="created_by",
            new_name="_old_created_by",
        ),

        # 2. Add new FK columns
        migrations.AddField(
            model_name="link",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_links",
                to="auth.user",
            ),
        ),
        migrations.AddField(
            model_name="link",
            name="project",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="links",
                to="projects.project",
            ),
        ),

        # 3. Data migration
        migrations.RunPython(resolve_identity_and_backfill_project, reverse_noop),

        # 4. Drop old column
        migrations.RemoveField(model_name="link", name="_old_created_by"),
    ]
