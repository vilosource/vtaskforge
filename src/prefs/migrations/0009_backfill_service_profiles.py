"""R2 (Bet B / scope S1): backfill fleet-agent users as service principals.

Every existing Agent-backed User becomes a fleet service principal
(UserProfile.user_type='service') so authorization recognises it by role
instance-wide, replacing the per-project ProjectMembership frame.
Forward-only data fix; reverse is a deliberate no-op (we never demote a
fleet principal back to a membership-scoped user). See
docs/fleet-principal-authorization-DESIGN.md.
"""

from django.db import migrations


def backfill_service_profiles(apps, schema_editor):
    Agent = apps.get_model("agents", "Agent")
    UserProfile = apps.get_model("prefs", "UserProfile")
    for agent in Agent.objects.exclude(user__isnull=True).select_related("user"):
        profile, created = UserProfile.objects.get_or_create(
            user_id=agent.user_id, defaults={"user_type": "service"}
        )
        if not created and profile.user_type != "service":
            profile.user_type = "service"
            profile.save(update_fields=["user_type", "updated_at"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("prefs", "0008_merge_phase9_session_id"),
        ("agents", "0004_backfill_agent_user"),
    ]

    operations = [
        migrations.RunPython(backfill_service_profiles, noop_reverse),
    ]
