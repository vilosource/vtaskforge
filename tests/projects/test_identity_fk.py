"""TDD tests for Project/Workplan/Milestone identity FK migration (Phase 0, Step 5).

Converts owner and created_by from CharField to FK User on Project, Workplan, Milestone.
Both are server-set from request.user on creation, read-only in v1 serializer.

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Step 5 DoD.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from projects.models import Project
from workplans.models import Workplan, Milestone
from tests.factories import ProjectFactory, WorkplanFactory, MilestoneFactory


@pytest.fixture
def staff_user(db):
    user = User.objects.create_user("staffuser", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return user, client


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProjectIdentity:

    def test_project_create_sets_owner(self, staff_user):
        user, client = staff_user
        response = client.post("/v1/projects/", {"name": "Test Project"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        project = Project.objects.get(id=response.data["id"])
        assert project.owner == user

    def test_project_create_sets_created_by(self, staff_user):
        user, client = staff_user
        response = client.post("/v1/projects/", {"name": "Test Project"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        project = Project.objects.get(id=response.data["id"])
        assert project.created_by == user

    def test_owner_read_only_v1(self, staff_user):
        """PATCH with owner should be ignored."""
        user, client = staff_user
        project = ProjectFactory(owner=user, created_by=user)
        other = User.objects.create_user("other-user")
        response = client.patch(
            f"/v1/projects/{project.id}/",
            {"owner": other.username},
            format="json",
        )
        assert response.status_code == 200
        project.refresh_from_db()
        assert project.owner == user  # Unchanged

    def test_created_by_read_only_v1(self, staff_user):
        """PATCH with created_by should be ignored."""
        user, client = staff_user
        project = ProjectFactory(owner=user, created_by=user)
        response = client.patch(
            f"/v1/projects/{project.id}/",
            {"created_by": "hacker"},
            format="json",
        )
        assert response.status_code == 200
        project.refresh_from_db()
        assert project.created_by == user

    def test_v1_serializer_owner_string(self, staff_user):
        user, client = staff_user
        project = ProjectFactory(owner=user, created_by=user)
        response = client.get(f"/v1/projects/{project.id}/")
        assert response.data["owner"] == user.username
        assert response.data["created_by"] == user.username


# ---------------------------------------------------------------------------
# Workplan
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestWorkplanIdentity:

    def test_workplan_create_sets_owner_created_by(self, staff_user):
        user, client = staff_user
        project = ProjectFactory(owner=user, created_by=user)
        response = client.post(
            "/v1/workplans/",
            {"name": "Test Workplan", "project": project.id},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        wp = Workplan.objects.get(id=response.data["id"])
        assert wp.owner == user
        assert wp.created_by == user


# ---------------------------------------------------------------------------
# Milestone
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMilestoneIdentity:

    def test_milestone_create_sets_created_by(self, staff_user):
        user, client = staff_user
        wp = WorkplanFactory()
        response = client.post(
            "/v1/milestones/",
            {"name": "Test Milestone", "workplan": wp.id},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        ms = Milestone.objects.get(id=response.data["id"])
        assert ms.created_by == user


# ---------------------------------------------------------------------------
# Data migration semantics
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDataMigrationSemantics:

    def test_project_with_user_fk(self):
        user = User.objects.create_user("proj-owner")
        project = Project.objects.create(name="Test", owner=user, created_by=user)
        project.refresh_from_db()
        assert project.owner == user
        assert project.created_by == user

    def test_workplan_with_user_fk(self):
        user = User.objects.create_user("wp-owner")
        project = ProjectFactory()
        wp = Workplan.objects.create(name="Test", project=project, owner=user, created_by=user)
        wp.refresh_from_db()
        assert wp.owner == user

    def test_milestone_with_user_fk(self):
        user = User.objects.create_user("ms-creator")
        wp = WorkplanFactory()
        ms = Milestone.objects.create(name="Test", workplan=wp, created_by=user)
        ms.refresh_from_db()
        assert ms.created_by == user
