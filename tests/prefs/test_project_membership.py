"""TDD tests for ProjectMembership model and auto-creation.

Phase 4 of User Management: advisory project membership.
"""

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import ProjectMembership


@pytest.mark.django_db
class TestProjectMembership:
    def test_create_membership(self):
        user = User.objects.create_user("user1", password="pass")
        membership = ProjectMembership.objects.create(
            user=user, project_id="proj1", role="member"
        )
        assert membership.pk is not None

    def test_unique_constraint_user_project(self):
        user = User.objects.create_user("user1", password="pass")
        ProjectMembership.objects.create(user=user, project_id="proj1")
        with pytest.raises(IntegrityError):
            ProjectMembership.objects.create(user=user, project_id="proj1")

    def test_auto_create_owner_on_project_create(self):
        """When a project is created via API, the creator gets owner membership."""
        user = User.objects.create_user("creator", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(
            "/v1/projects/",
            {"name": "Test Project"},
            format="json",
        )

        assert response.status_code == 201
        project_id = response.json()["id"]
        assert ProjectMembership.objects.filter(
            user=user, project_id=project_id, role="owner"
        ).exists()

    def test_list_memberships_for_user(self):
        user = User.objects.create_user("user1", password="pass")
        ProjectMembership.objects.create(user=user, project_id="p1", role="owner")
        ProjectMembership.objects.create(user=user, project_id="p2", role="member")
        assert ProjectMembership.objects.filter(user=user).count() == 2

    def test_validate_endpoint_includes_projects(self):
        user = User.objects.create_user("user1", password="pass")
        token = Token.objects.create(user=user)
        ProjectMembership.objects.create(user=user, project_id="proj-a", role="owner")
        ProjectMembership.objects.create(user=user, project_id="proj-b", role="member")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/auth/validate/")

        projects = response.json()["projects"]
        assert len(projects) == 2
        project_ids = [p["project_id"] for p in projects]
        assert "proj-a" in project_ids
        assert "proj-b" in project_ids

    def test_membership_roles(self):
        user = User.objects.create_user("user1", password="pass")
        for role in ["owner", "member", "viewer"]:
            m = ProjectMembership.objects.create(
                user=user, project_id=f"proj-{role}", role=role
            )
            assert m.role == role
