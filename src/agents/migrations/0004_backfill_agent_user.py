"""Data migration: backfill Agent.user FK from User.username == Agent.id.

Phase 0, Step 1: Links existing Agents to their corresponding Users.
Agents without a matching User are left with user=None (pre-provisioned state).
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def backfill_agent_user(apps, schema_editor):
    Agent = apps.get_model("agents", "Agent")
    User = apps.get_model("auth", "User")

    user_map = {u.username: u for u in User.objects.all()}

    linked = 0
    skipped = 0
    for agent in Agent.objects.filter(user__isnull=True).iterator():
        user = user_map.get(agent.id)
        if user:
            agent.user = user
            agent.save(update_fields=["user"])
            linked += 1
        else:
            skipped += 1
            logger.warning(f"Agent '{agent.id}' ({agent.name}) has no matching User")

    logger.info(f"Backfilled Agent.user: {linked} linked, {skipped} skipped")


def reverse_backfill(apps, schema_editor):
    Agent = apps.get_model("agents", "Agent")
    Agent.objects.all().update(user=None)


class Migration(migrations.Migration):
    dependencies = [
        ("agents", "0003_add_user_fk"),
    ]

    operations = [
        migrations.RunPython(backfill_agent_user, reverse_backfill),
    ]
