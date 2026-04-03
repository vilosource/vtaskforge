"""Convert Note.actor_id CharField to Note.actor FK User.

Phase 0, Step 4: Rename old column, add FK, resolve, drop old.
"""

import logging

from django.db import migrations, models
import django.db.models.deletion

logger = logging.getLogger(__name__)


def resolve_note_actors(apps, schema_editor):
    User = apps.get_model("auth", "User")
    user_map = {u.username: u.pk for u in User.objects.all()}

    from django.db import connections
    cursor = connections[schema_editor.connection.alias].cursor()
    cursor.execute("SELECT id, _old_actor_id FROM tasks_note")

    stats = {"resolved": 0, "unresolvable": 0, "empty": 0}
    for row in cursor.fetchall():
        note_id, old_val = row
        if not old_val or old_val.strip() == "":
            stats["empty"] += 1
            continue
        user_pk = user_map.get(old_val)
        if user_pk:
            cursor.execute("UPDATE tasks_note SET actor_id = %s WHERE id = %s", [user_pk, note_id])
            stats["resolved"] += 1
        else:
            stats["unresolvable"] += 1
            logger.warning(f"Unresolvable actor_id '{old_val}' on note {note_id}")

    logger.info(f"Note actor migration: {stats}")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0012_convert_identity_fields_to_fk"),
        ("auth", "__first__"),
    ]

    operations = [
        migrations.RenameField(model_name="note", old_name="actor_id", new_name="_old_actor_id"),
        migrations.AddField(
            model_name="note", name="actor",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="task_notes", to="auth.user",
            ),
        ),
        migrations.RunPython(resolve_note_actors, reverse_noop),
        migrations.RemoveField(model_name="note", name="_old_actor_id"),
    ]
