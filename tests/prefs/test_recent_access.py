"""TDD tests for recently accessed feature.

Covers: models, service (upsert/trim/agent exclusion), API endpoint, ViewSet mixin.
"""

import json

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from prefs.models import RecentAccess, UserProfile
from prefs.services import record_access
from tests.factories import ProjectFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Step 1: Models
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecentAccessModel:
    def test_create_access_record(self):
        user = User.objects.create_user("human", password="pass")
        access = RecentAccess.objects.create(
            user=user,
            resource_type="task",
            resource_id="abc123",
            resource_title="Add auth endpoint",
            resource_status="doing",
        )
        assert access.pk is not None
        assert access.resource_type == "task"

    def test_ordering_is_most_recent_first(self):
        user = User.objects.create_user("human2", password="pass")
        a1 = RecentAccess.objects.create(user=user, resource_type="task", resource_id="t1", resource_title="First")
        a2 = RecentAccess.objects.create(user=user, resource_type="task", resource_id="t2", resource_title="Second")
        recent = list(RecentAccess.objects.filter(user=user))
        assert recent[0].resource_id == "t2"

    def test_unique_constraint_per_user_resource(self):
        from django.db import IntegrityError
        user = User.objects.create_user("human3", password="pass")
        RecentAccess.objects.create(user=user, resource_type="task", resource_id="t1", resource_title="Task 1")
        with pytest.raises(IntegrityError):
            RecentAccess.objects.create(user=user, resource_type="task", resource_id="t1", resource_title="Task 1 dup")


@pytest.mark.django_db
class TestUserProfileModel:
    def test_profile_created_for_user(self):
        user = User.objects.create_user("human4", password="pass")
        profile = UserProfile.objects.create(user=user)
        assert profile.pk is not None
        assert profile.user == user


# ---------------------------------------------------------------------------
# Step 2: Service — record_access
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecordAccessService:
    def test_creates_access_record(self):
        user = User.objects.create_user("svc1", password="pass")
        record_access(user, "task", "t1", "My Task", "doing")
        assert RecentAccess.objects.filter(user=user).count() == 1

    def test_upsert_updates_timestamp_not_duplicate(self):
        user = User.objects.create_user("svc2", password="pass")
        record_access(user, "task", "t1", "My Task", "doing")
        record_access(user, "task", "t1", "My Task Updated", "done")
        assert RecentAccess.objects.filter(user=user).count() == 1
        access = RecentAccess.objects.get(user=user, resource_id="t1")
        assert access.resource_title == "My Task Updated"
        assert access.resource_status == "done"

    def test_trims_to_20(self):
        user = User.objects.create_user("svc3", password="pass")
        for i in range(25):
            record_access(user, "task", f"t{i}", f"Task {i}")
        assert RecentAccess.objects.filter(user=user).count() == 20

    def test_excludes_agent_users(self):
        """Agents are created without a usable password."""
        agent_user = User.objects.create_user("agent-executor-1")  # No password
        record_access(agent_user, "task", "t1", "Task 1")
        assert RecentAccess.objects.filter(user=agent_user).count() == 0

    def test_excludes_anonymous_users(self):
        from django.contrib.auth.models import AnonymousUser
        record_access(AnonymousUser(), "task", "t1", "Task 1")
        assert RecentAccess.objects.count() == 0

    def test_different_resource_types_not_conflicting(self):
        user = User.objects.create_user("svc4", password="pass")
        record_access(user, "task", "id1", "Task")
        record_access(user, "project", "id1", "Project")
        assert RecentAccess.objects.filter(user=user).count() == 2


# ---------------------------------------------------------------------------
# Step 3: API endpoint — GET /v1/profile/recent/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecentAccessAPI:
    def test_returns_recent_accesses(self):
        user = User.objects.create_user("api1", password="pass")
        record_access(user, "task", "t1", "Task One", "doing")
        record_access(user, "project", "p1", "My Project", "active")

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/v1/profile/recent/")

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["results"][0]["resource_type"] == "project"  # Most recent first
        assert data["results"][1]["resource_type"] == "task"

    def test_returns_empty_for_new_user(self):
        user = User.objects.create_user("api2", password="pass")
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/v1/profile/recent/")
        assert response.status_code == 200
        assert len(response.json()["results"]) == 0

    def test_rejects_agent_token(self):
        from rest_framework.authtoken.models import Token
        agent_user = User.objects.create_user("agent-1")  # No password = agent
        token = Token.objects.create(user=agent_user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/profile/recent/")
        assert response.status_code == 403

    def test_rejects_unauthenticated(self):
        client = APIClient()
        response = client.get("/v1/profile/recent/")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Step 4: ViewSet mixin — auto-records on retrieve
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTrackAccessMixin:
    def test_task_detail_records_access(self):
        user = User.objects.create_user("mix1", password="pass")
        project = ProjectFactory()
        workplan = WorkplanFactory(project=project, status="active")
        task = TaskFactory(project=project, workplan=workplan, status="todo")

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == 200

        accesses = RecentAccess.objects.filter(user=user)
        assert accesses.count() == 1
        assert accesses[0].resource_type == "task"
        assert accesses[0].resource_id == task.id
        assert accesses[0].resource_title == task.title

    def test_project_detail_records_access(self):
        user = User.objects.create_user("mix2", password="pass")
        project = ProjectFactory()

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(f"/v1/projects/{project.id}/")
        assert response.status_code == 200

        accesses = RecentAccess.objects.filter(user=user)
        assert accesses.count() == 1
        assert accesses[0].resource_type == "project"

    def test_agent_detail_does_not_record(self):
        agent_user = User.objects.create_user("agent-mix")
        from rest_framework.authtoken.models import Token
        token = Token.objects.create(user=agent_user)
        project = ProjectFactory()
        task = TaskFactory(project=project, status="todo")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == 200

        assert RecentAccess.objects.filter(user=agent_user).count() == 0
