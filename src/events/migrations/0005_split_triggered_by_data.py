"""Data migration: split triggered_by into trigger_source + actor.

Phase 0, Step 2: Resolves existing triggered_by values:
- Known action labels → trigger_source only
- Resolvable usernames/agent IDs → trigger_source (inferred) + actor FK
- Empty strings → both empty/null
- Unresolvable values → preserved in trigger_source, logged

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Section 1.3
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

# Known action labels that are NOT identity references
ACTION_LABELS = frozenset({
    "submit", "system", "admin", "complete", "fail",
    "recover", "resubmit", "block", "unblock", "defer",
    "cancel", "unclaim", "review", "progress",
})

# Map event_type → likely trigger_source for events where triggered_by was an agent ID
EVENT_TYPE_TO_SOURCE = {
    "status_changed": "transition",
    "claimed": "claim",
    "unclaimed": "unclaim",
    "claim_expired": "system",
    "review_submitted": "review",
    "link_added": "link",
    "link_removed": "link",
    "field_updated": "update",
    "force_transition": "admin",
    "note": "note",
}


def split_triggered_by(apps, schema_editor):
    TaskEvent = apps.get_model("events", "TaskEvent")
    User = apps.get_model("auth", "User")

    user_map = {u.username: u for u in User.objects.all()}

    stats = {"action_label": 0, "resolved": 0, "unresolvable": 0, "empty": 0}

    for event in TaskEvent.objects.all().iterator():
        value = event.triggered_by

        if not value:
            event.trigger_source = ""
            event.actor = None
            stats["empty"] += 1
        elif value in ACTION_LABELS:
            event.trigger_source = value
            event.actor = None
            stats["action_label"] += 1
        elif value in user_map:
            event.trigger_source = EVENT_TYPE_TO_SOURCE.get(event.event_type, "")
            event.actor = user_map[value]
            stats["resolved"] += 1
        else:
            event.trigger_source = value
            event.actor = None
            stats["unresolvable"] += 1
            logger.warning(
                f"Unresolvable triggered_by='{value}' on event {event.id} "
                f"(type={event.event_type})"
            )

        event.save(update_fields=["trigger_source", "actor"])

    logger.info(
        f"Split triggered_by: {stats['resolved']} resolved, "
        f"{stats['action_label']} action labels, "
        f"{stats['empty']} empty, "
        f"{stats['unresolvable']} unresolvable"
    )


def reverse_split(apps, schema_editor):
    """Reverse: copy trigger_source or actor.username back to triggered_by."""
    TaskEvent = apps.get_model("events", "TaskEvent")
    for event in TaskEvent.objects.select_related("actor").all().iterator():
        if event.actor:
            event.triggered_by = event.actor.username
        else:
            event.triggered_by = event.trigger_source
        event.save(update_fields=["triggered_by"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0004_add_trigger_source_and_actor"),
    ]

    operations = [
        migrations.RunPython(split_triggered_by, reverse_split),
    ]
