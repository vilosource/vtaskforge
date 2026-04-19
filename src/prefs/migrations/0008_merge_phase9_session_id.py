# Merge migration — reconciles 0007 (session_id field) with 0006 (pre-existing
# data bootstrap with a known bug at owner_id). Empty operations list: both
# parents already produce the desired state independently.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('prefs', '0006_bootstrap_project_memberships'),
        ('prefs', '0007_sessionrecord_session_id'),
    ]

    operations = []
