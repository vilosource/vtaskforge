"""Bootstrap ProjectMembership records for existing data.

Creates memberships based on existing activity so that Step 7 authorization
does not lock out existing non-staff users.
"""

from django.db import migrations


def bootstrap_memberships(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Task = apps.get_model("tasks", "Task")
    Workplan = apps.get_model("workplans", "Workplan")
    ProjectMembership = apps.get_model("prefs", "ProjectMembership")

    for project in Project.objects.all():
        user_ids_owner = set()
        user_ids_member = set()

        # Project owner
        if project.owner_id:
            user_ids_owner.add(project.owner_id)
        # Project created_by
        if project.created_by_id:
            user_ids_member.add(project.created_by_id)

        # Task creators, assignees, claimers
        task_fields = Task.objects.filter(project=project).values_list(
            "created_by_id", "assigned_to_id", "claimed_by_id"
        )
        for created_by, assigned_to, claimed_by in task_fields:
            if created_by:
                user_ids_member.add(created_by)
            if assigned_to:
                user_ids_member.add(assigned_to)
            if claimed_by:
                user_ids_member.add(claimed_by)

        # Workplan owners and creators
        wp_fields = Workplan.objects.filter(project=project).values_list(
            "owner_id", "created_by_id"
        )
        for owner_id, created_by in wp_fields:
            if owner_id:
                user_ids_member.add(owner_id)
            if created_by:
                user_ids_member.add(created_by)

        # Remove owner IDs from member set to avoid conflicts
        user_ids_member -= user_ids_owner

        # Create owner memberships
        for uid in user_ids_owner:
            ProjectMembership.objects.get_or_create(
                user_id=uid,
                project_id=project.id,
                defaults={"role": "owner"},
            )

        # Create member memberships
        for uid in user_ids_member:
            ProjectMembership.objects.get_or_create(
                user_id=uid,
                project_id=project.id,
                defaults={"role": "member"},
            )


def reverse_bootstrap(apps, schema_editor):
    # No-op: we don't want to delete memberships on reverse
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("prefs", "0005_projectmembership_and_more"),
        ("projects", "0001_initial"),
        ("tasks", "0001_initial"),
        ("workplans", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(bootstrap_memberships, reverse_bootstrap),
    ]
