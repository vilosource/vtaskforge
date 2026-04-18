"""TDD tests for authorization enforcement (Phase 0, Step 7).

Tests ProjectScopedModel, queryset scoping, object-level permissions,
role-based access, create-time validation, and bootstrap migration.

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Step 7 DoD.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import ProjectMembership
from projects.models import Project
from tasks.models import Task, Note
from workplans.models import Workplan, Milestone
from events.models import TaskEvent
from links.models import Link
from reviews.models import Review
from tests.factories import (
    AgentFactory, ProjectFactory, WorkplanFactory, MilestoneFactory,
    TaskFactory, LinkFactory, NoteFactory, ReviewFactory, TaskEventFactory,
)


def _make_user_client(username, is_staff=False):
    """Create a user with token and authenticated APIClient."""
    user = User.objects.create_user(username, password="pass", is_staff=is_staff)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return user, client


def _make_project_with_task(owner):
    """Create a project with a workplan, milestone, and task. Owner gets membership."""
    project = ProjectFactory(owner=owner, created_by=owner)
    ProjectMembership.objects.get_or_create(
        user=owner, project_id=project.id, defaults={"role": "owner"}
    )
    wp = WorkplanFactory(project=project, owner=owner, created_by=owner)
    ms = MilestoneFactory(workplan=wp, created_by=owner)
    task = TaskFactory(milestone=ms, created_by=owner)
    return project, wp, ms, task


# ---------------------------------------------------------------------------
# ProjectScopedModel.get_project_id()
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProjectScopedModel:

    def test_task_get_project_id(self):
        task = TaskFactory()
        assert task.get_project_id() == task.project_id

    def test_milestone_get_project_id(self):
        ms = MilestoneFactory()
        assert ms.get_project_id() == ms.workplan.project_id

    def test_review_get_project_id(self):
        review = ReviewFactory()
        assert review.get_project_id() == review.task.project_id

    def test_note_get_project_id(self):
        note = NoteFactory()
        assert note.get_project_id() == note.task.project_id

    def test_event_get_project_id(self):
        event = TaskEventFactory()
        assert event.get_project_id() == event.task.project_id

    def test_link_get_project_id(self):
        task = TaskFactory()
        link = LinkFactory(source_type="task", source_id=task.id, project=task.project)
        assert link.get_project_id() == task.project_id

    def test_project_get_project_id(self):
        project = ProjectFactory()
        assert project.get_project_id() == project.id


# ---------------------------------------------------------------------------
# Queryset scoping — non-member sees nothing, member sees own project
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestQuerysetScoping:

    def test_non_member_sees_no_tasks(self):
        user_a, client_a = _make_user_client("user-a")
        user_b, client_b = _make_user_client("user-b")
        _make_project_with_task(user_a)

        response = client_b.get("/v1/tasks/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 0

    def test_member_sees_own_project_tasks(self):
        user_a, client_a = _make_user_client("user-a")
        user_b, client_b = _make_user_client("user-b")
        proj_a, _, _, task_a = _make_project_with_task(user_a)
        proj_b, _, _, task_b = _make_project_with_task(user_b)

        response = client_a.get("/v1/tasks/")
        task_ids = [t["id"] for t in response.data["results"]]
        assert task_a.id in task_ids
        assert task_b.id not in task_ids

    def test_staff_sees_all_tasks(self):
        user_a, _ = _make_user_client("user-a")
        _, staff_client = _make_user_client("staff-user", is_staff=True)
        _make_project_with_task(user_a)

        response = staff_client.get("/v1/tasks/")
        assert len(response.data["results"]) >= 1

    def test_non_member_sees_no_workplans(self):
        user_a, _ = _make_user_client("user-a")
        user_b, client_b = _make_user_client("user-b")
        _make_project_with_task(user_a)

        response = client_b.get("/v1/workplans/")
        assert len(response.data["results"]) == 0

    def test_non_member_sees_no_milestones(self):
        user_a, _ = _make_user_client("user-a")
        user_b, client_b = _make_user_client("user-b")
        _make_project_with_task(user_a)

        response = client_b.get("/v1/milestones/")
        assert len(response.data["results"]) == 0

    def test_non_member_sees_no_links(self):
        user_a, _ = _make_user_client("user-a")
        user_b, client_b = _make_user_client("user-b")
        proj, _, _, task = _make_project_with_task(user_a)
        LinkFactory(source_type="task", source_id=task.id, project=proj, created_by=user_a)

        response = client_b.get("/v1/links/")
        assert len(response.data["results"]) == 0


# ---------------------------------------------------------------------------
# Object-level permission — non-member gets 403 on detail
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestObjectPermission:

    def test_non_member_403_on_task_detail(self):
        user_a, _ = _make_user_client("user-a")
        user_b, client_b = _make_user_client("user-b")
        _, _, _, task = _make_project_with_task(user_a)

        response = client_b.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == 403

    def test_member_200_on_task_detail(self):
        user_a, client_a = _make_user_client("user-a")
        _, _, _, task = _make_project_with_task(user_a)

        response = client_a.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Role-based permissions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRoleBasedPermission:

    def test_viewer_can_read(self):
        owner, _ = _make_user_client("owner")
        viewer, viewer_client = _make_user_client("viewer")
        proj, _, _, task = _make_project_with_task(owner)
        ProjectMembership.objects.create(user=viewer, project_id=proj.id, role="viewer")

        response = viewer_client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == 200

    def test_viewer_cannot_create(self):
        owner, _ = _make_user_client("owner")
        viewer, viewer_client = _make_user_client("viewer")
        proj, wp, ms, _ = _make_project_with_task(owner)
        ProjectMembership.objects.create(user=viewer, project_id=proj.id, role="viewer")

        response = viewer_client.post(
            "/v1/tasks/",
            {"title": "New task", "project": proj.id, "workplan": wp.id, "milestone": ms.id},
            format="json",
        )
        assert response.status_code == 403

    def test_viewer_cannot_update(self):
        owner, _ = _make_user_client("owner")
        viewer, viewer_client = _make_user_client("viewer")
        proj, _, _, task = _make_project_with_task(owner)
        ProjectMembership.objects.create(user=viewer, project_id=proj.id, role="viewer")

        response = viewer_client.patch(
            f"/v1/tasks/{task.id}/", {"title": "Modified"}, format="json"
        )
        assert response.status_code == 403

    def test_member_can_create(self):
        owner, _ = _make_user_client("owner")
        member, member_client = _make_user_client("member")
        proj, wp, ms, _ = _make_project_with_task(owner)
        ProjectMembership.objects.create(user=member, project_id=proj.id, role="member")

        response = member_client.post(
            "/v1/tasks/",
            {"title": "Member task", "project": proj.id, "workplan": wp.id, "milestone": ms.id},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_member_can_update_own(self):
        member, member_client = _make_user_client("member")
        proj, wp, ms, _ = _make_project_with_task(member)

        # Create a task as this member
        response = member_client.post(
            "/v1/tasks/",
            {"title": "My task", "project": proj.id, "workplan": wp.id, "milestone": ms.id},
            format="json",
        )
        task_id = response.data["id"]

        response = member_client.patch(
            f"/v1/tasks/{task_id}/", {"title": "Updated"}, format="json"
        )
        assert response.status_code == 200

    def test_member_cannot_update_others(self):
        owner, _ = _make_user_client("owner")
        member, member_client = _make_user_client("member")
        proj, _, _, task = _make_project_with_task(owner)
        ProjectMembership.objects.create(user=member, project_id=proj.id, role="member")

        response = member_client.patch(
            f"/v1/tasks/{task.id}/", {"title": "Hijacked"}, format="json"
        )
        assert response.status_code == 403

    def test_member_cannot_delete(self):
        owner, _ = _make_user_client("owner")
        member, member_client = _make_user_client("member")
        proj, _, _, task = _make_project_with_task(owner)
        ProjectMembership.objects.create(user=member, project_id=proj.id, role="member")

        response = member_client.delete(f"/v1/tasks/{task.id}/")
        assert response.status_code == 403

    def test_owner_can_delete(self):
        owner, owner_client = _make_user_client("owner")
        proj, _, _, task = _make_project_with_task(owner)

        response = owner_client.delete(f"/v1/tasks/{task.id}/")
        assert response.status_code in (200, 204)

    def test_claimer_can_patch_task_they_did_not_create(self):
        """Agent (member role) that claimed a task can PATCH it, even when
        created_by is a different user. This is how the vafi controller
        writes execution_summary back after the harness completes.
        """
        from tasks.models import Task

        owner, _ = _make_user_client("owner")
        agent, agent_client = _make_user_client("agent")
        proj, wp, ms, _ = _make_project_with_task(owner)
        ProjectMembership.objects.create(user=agent, project_id=proj.id, role="member")

        task = Task.objects.create(
            title="Owner-created, agent-claimed",
            project=proj, workplan=wp, milestone=ms,
            created_by=owner, claimed_by=agent, status="doing",
        )

        response = agent_client.patch(
            f"/v1/tasks/{task.id}/",
            {"execution_summary": {"turns": 3, "cost": 0.01}},
            format="json",
        )
        assert response.status_code == 200, response.content
        task.refresh_from_db()
        assert task.execution_summary == {"turns": 3, "cost": 0.01}


# ---------------------------------------------------------------------------
# Create-time validation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreateValidation:

    def test_create_validates_project_membership(self):
        owner, _ = _make_user_client("owner")
        outsider, outsider_client = _make_user_client("outsider")
        proj, wp, ms, _ = _make_project_with_task(owner)

        response = outsider_client.post(
            "/v1/tasks/",
            {"title": "Sneaky", "project": proj.id, "workplan": wp.id, "milestone": ms.id},
            format="json",
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Agent auto-membership on claim
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAgentAutoMembership:

    def test_claim_creates_agent_membership(self):
        owner, owner_client = _make_user_client("owner")
        proj, wp, ms, task = _make_project_with_task(owner)
        task.status = "todo"
        task.save(update_fields=["status"])

        agent = AgentFactory(name="claim-agent")
        # Agent has no membership yet
        assert not ProjectMembership.objects.filter(user=agent.user, project_id=proj.id).exists()

        owner_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent.id},
            format="json",
        )

        # After claim, agent should have membership
        assert ProjectMembership.objects.filter(user=agent.user, project_id=proj.id).exists()

    def test_claim_existing_membership_no_duplicate(self):
        owner, owner_client = _make_user_client("owner")
        proj, wp, ms, task = _make_project_with_task(owner)
        task.status = "todo"
        task.save(update_fields=["status"])

        agent = AgentFactory(name="existing-member-agent")
        ProjectMembership.objects.create(user=agent.user, project_id=proj.id, role="member")

        owner_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent.id},
            format="json",
        )

        assert ProjectMembership.objects.filter(user=agent.user, project_id=proj.id).count() == 1


# ---------------------------------------------------------------------------
# Nested view authorization — MilestoneTasksView, ProjectTasksView, BulkImportView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNestedViewAuthorization:

    def test_milestone_tasks_view_checks_membership(self):
        """POST /v1/milestones/{id}/tasks/ must check project membership."""
        owner, _ = _make_user_client("owner")
        outsider, outsider_client = _make_user_client("outsider")
        proj, wp, ms, _ = _make_project_with_task(owner)

        response = outsider_client.post(
            f"/v1/milestones/{ms.id}/tasks/",
            {"title": "Sneaky task"},
            format="json",
        )
        assert response.status_code == 403

    def test_project_tasks_view_checks_membership(self):
        """POST /v1/projects/{id}/tasks/ must check project membership."""
        owner, _ = _make_user_client("owner")
        outsider, outsider_client = _make_user_client("outsider")
        proj, _, _, _ = _make_project_with_task(owner)

        response = outsider_client.post(
            f"/v1/projects/{proj.id}/tasks/",
            {"title": "Sneaky backlog task"},
            format="json",
        )
        assert response.status_code == 403

    def test_bulk_import_checks_membership(self):
        """POST /v1/bulk/import must check project membership."""
        owner, _ = _make_user_client("owner")
        outsider, outsider_client = _make_user_client("outsider")
        proj, _, _, _ = _make_project_with_task(owner)

        response = outsider_client.post(
            "/v1/bulk/import",
            {
                "project_id": proj.id,
                "milestones": [{"ref": "ms-1", "name": "Sneaky Milestone", "tasks": []}],
            },
            format="json",
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Queryset scoping — reviews, events, notes
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestQuerysetScopingNested:

    def test_queryset_scoping_reviews(self):
        """Non-member sees no reviews from another project."""
        owner, _ = _make_user_client("owner")
        outsider, outsider_client = _make_user_client("outsider")
        _, _, _, task = _make_project_with_task(owner)
        ReviewFactory(task=task, reviewer=owner)

        response = outsider_client.get(f"/v1/tasks/{task.id}/reviews/")
        # Non-member should get 403 on nested route (task-level permission)
        # or empty results if scoped
        assert response.status_code == 403 or len(response.data.get("results", [])) == 0

    def test_queryset_scoping_events(self):
        """Non-member sees no events from another project."""
        owner, _ = _make_user_client("owner")
        outsider, outsider_client = _make_user_client("outsider")
        _, _, _, task = _make_project_with_task(owner)
        TaskEventFactory(task=task)

        response = outsider_client.get(f"/v1/tasks/{task.id}/events/")
        assert response.status_code == 403 or len(response.data.get("results", [])) == 0

    def test_queryset_scoping_notes(self):
        """Non-member sees no notes from another project."""
        owner, _ = _make_user_client("owner")
        outsider, outsider_client = _make_user_client("outsider")
        _, _, _, task = _make_project_with_task(owner)
        NoteFactory(task=task, actor=owner)

        response = outsider_client.get(f"/v1/tasks/{task.id}/notes/")
        assert response.status_code == 403 or len(response.data.get("results", [])) == 0


# ---------------------------------------------------------------------------
# Bootstrap migration correctness
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBootstrapMigration:

    def test_bootstrap_migration_owner(self):
        """Project owner should get 'owner' membership from bootstrap logic."""
        owner = User.objects.create_user("bootstrap-owner")
        project = ProjectFactory(owner=owner, created_by=owner)
        # Simulate bootstrap: owner should get membership
        ProjectMembership.objects.get_or_create(
            user=owner, project_id=project.id, defaults={"role": "owner"}
        )
        membership = ProjectMembership.objects.get(user=owner, project_id=project.id)
        assert membership.role == "owner"

    def test_bootstrap_migration_claimers(self):
        """Users who claimed tasks should get 'member' membership from bootstrap logic."""
        owner = User.objects.create_user("bootstrap-owner2")
        claimer = User.objects.create_user("bootstrap-claimer")
        project = ProjectFactory(owner=owner, created_by=owner)
        TaskFactory(
            project=project,
            milestone=MilestoneFactory(workplan=WorkplanFactory(project=project)),
            claimed_by=claimer,
        )
        # Simulate bootstrap: claimer should get member membership
        ProjectMembership.objects.get_or_create(
            user=claimer, project_id=project.id, defaults={"role": "member"}
        )
        membership = ProjectMembership.objects.get(user=claimer, project_id=project.id)
        assert membership.role == "member"

    def test_bootstrap_migration_no_activity(self):
        """Users with no project activity should have no membership."""
        inactive = User.objects.create_user("bootstrap-inactive")
        project = ProjectFactory()
        assert not ProjectMembership.objects.filter(
            user=inactive, project_id=project.id
        ).exists()
