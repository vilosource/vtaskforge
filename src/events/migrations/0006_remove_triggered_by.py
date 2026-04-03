"""Remove deprecated triggered_by CharField after data migration.

Phase 0, Step 2: The triggered_by field has been split into
trigger_source + actor. This migration drops the old column.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0005_split_triggered_by_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="taskevent",
            name="triggered_by",
        ),
    ]
