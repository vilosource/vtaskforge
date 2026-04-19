# Phase 9 Pre-Phase 0: add session_id to SessionRecord so the bridge can map
# JSONL session_id -> user for the Phase 9 history endpoint's attribution.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Depend on 0005 (schema) not 0006 (data migration that has a
        # pre-existing bug referring to project.owner_id). 0007 is pure
        # schema; ordering relative to the data bootstrap doesn't matter.
        ('prefs', '0005_projectmembership_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sessionrecord',
            name='session_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=255),
        ),
    ]
