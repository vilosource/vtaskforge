"""
Split Task.requires into requires (deps) + required_tags (capabilities).

Historically, Task.requires JSONField was used by two unrelated concerns:
  1. capability tag strings ("executor", "pi") consumed by
     find_claimable_tasks for agent matching
  2. task dependency reference dicts ({id: ..., title: ...}) typed as
     TaskRef in the SDK

Both lived in the same field. The SDK's typed list[TaskRef] crashed on
string values, and the CLI's --requires option was internally confused
about which it meant. This migration:

  - Adds Task.required_tags (JSONField) for capability tag strings.
  - Walks every existing Task and partitions Task.requires:
       bare strings  -> required_tags
       dict-shaped   -> stay in requires
       anything else -> dropped (logged as a migration warning; should not
                        happen in practice but the data is best-effort)
  - Leaves Task.requires non-nullable list-default-empty as-is so existing
    consumers reading deps still see the same shape.

Down-migration restores the union: required_tags entries are merged back
into requires alongside whatever dep refs were there. This is best-effort
since the original ordering isn't preserved.
"""
from django.db import migrations, models


def _split_requires(apps, schema_editor):
    from tasks.requires_partition import partition_requires
    Task = apps.get_model("tasks", "Task")
    for task in Task.objects.all().iterator():
        deps, tags = partition_requires(task.requires)
        task.requires = deps
        task.required_tags = tags
        task.save(update_fields=["requires", "required_tags"])


def _merge_back(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    for task in Task.objects.all().iterator():
        deps = task.requires or []
        tags = task.required_tags or []
        merged = list(deps) + list(tags)
        task.requires = merged
        task.save(update_fields=["requires"])


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0013_convert_note_actor_to_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="required_tags",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(_split_requires, _merge_back),
    ]
