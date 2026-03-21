# Generated manually on 2026-03-21 17:29

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
        ('workplans', '0006_populate_project_for_workplans'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workplan',
            name='project',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='workplans',
                to='projects.project'
            ),
        ),
    ]