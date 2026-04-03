"""Convert Task identity fields from CharField to FK User.

Phase 0, Step 3: Three-phase migration:
1. Rename old CharField columns (assigned_to → _old_assigned_to, etc.)
2. Add new FK columns with the original names
3. Data migration: resolve string values to User PKs
4. Drop old columns

This avoids Django's AlterField which would try to cast varchar→integer.
"""

import logging

from django.db import migrations, models
import django.db.models.deletion

logger = logging.getLogger(__name__)


def resolve_identity_fields(apps, schema_editor):
    """Populate new FK columns from old string columns."""
    Task = apps.get_model("tasks", "Task")
    User = apps.get_model("auth", "User")

    user_map = {u.username: u.pk for u in User.objects.all()}

    stats = {"resolved": 0, "unresolvable": 0, "empty": 0}
    field_map = [
        ("_old_assigned_to", "assigned_to_id"),
        ("_old_claimed_by", "claimed_by_id"),
        ("_old_created_by", "created_by_id"),
    ]

    # Use raw SQL to read old columns since Django ORM doesn't know about them
    db_alias = schema_editor.connection.alias
    from django.db import connections
    cursor = connections[db_alias].cursor()

    cursor.execute("SELECT id, _old_assigned_to, _old_claimed_by, _old_created_by FROM tasks_task")
    for row in cursor.fetchall():
        task_id, old_assigned, old_claimed, old_created = row
        updates = {}

        for old_val, new_col in [(old_assigned, "assigned_to_id"),
                                  (old_claimed, "claimed_by_id"),
                                  (old_created, "created_by_id")]:
            if not old_val or old_val.strip() == "":
                stats["empty"] += 1
                continue

            user_pk = user_map.get(old_val)
            if user_pk:
                updates[new_col] = user_pk
                stats["resolved"] += 1
            else:
                stats["unresolvable"] += 1
                logger.warning(f"Unresolvable identity '{old_val}' on task {task_id}")

        if updates:
            set_clause = ", ".join(f"{col} = %s" for col in updates.keys())
            cursor.execute(
                f"UPDATE tasks_task SET {set_clause} WHERE id = %s",
                list(updates.values()) + [task_id],
            )

    logger.info(f"Task identity migration: {stats}")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0011_task_execution_summary"),
        ("auth", "__first__"),
    ]

    operations = [
        # 1. Rename old CharField columns
        migrations.RenameField(
            model_name="task",
            old_name="assigned_to",
            new_name="_old_assigned_to",
        ),
        migrations.RenameField(
            model_name="task",
            old_name="claimed_by",
            new_name="_old_claimed_by",
        ),
        migrations.RenameField(
            model_name="task",
            old_name="created_by",
            new_name="_old_created_by",
        ),

        # 2. Add new FK columns
        migrations.AddField(
            model_name="task",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_tasks",
                to="auth.user",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="claimed_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="claimed_tasks",
                to="auth.user",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_tasks",
                to="auth.user",
            ),
        ),

        # 3. Data migration
        migrations.RunPython(resolve_identity_fields, reverse_noop),

        # 4. Drop old columns
        migrations.RemoveField(model_name="task", name="_old_assigned_to"),
        migrations.RemoveField(model_name="task", name="_old_claimed_by"),
        migrations.RemoveField(model_name="task", name="_old_created_by"),
    ]
