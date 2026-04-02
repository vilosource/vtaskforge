"""TDD tests for access enforcement via ProjectMembership.

Phase 6 of User Management: project-scoped access control.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import ProjectMembership
from tests.factories import ProjectFactory


@pytest.mark.django_db
class TestAccessEnforcement:
    def test_non_member_gets_403_on_project_endpoint(self):
        user = User.objects.create_user("outsider", password="pass")
        token = Token.objects.create(user=user)
        project = ProjectFactory()

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(f"/v1/projects/{project.id}/workplans/")
        assert response.status_code == 403

    def test_member_gets_200(self):
        user = User.objects.create_user("member1", password="pass")
        token = Token.objects.create(user=user)
        project = ProjectFactory()
        ProjectMembership.objects.create(user=user, project_id=project.id, role="member")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(f"/v1/projects/{project.id}/workplans/")
        assert response.status_code == 200

    def test_owner_gets_200(self):
        user = User.objects.create_user("owner1", password="pass")
        token = Token.objects.create(user=user)
        project = ProjectFactory()
        ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(f"/v1/projects/{project.id}/workplans/")
        assert response.status_code == 200

    def test_viewer_gets_200_on_read(self):
        user = User.objects.create_user("viewer1", password="pass")
        token = Token.objects.create(user=user)
        project = ProjectFactory()
        ProjectMembership.objects.create(user=user, project_id=project.id, role="viewer")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(f"/v1/projects/{project.id}/workplans/")
        assert response.status_code == 200

    def test_staff_bypasses_membership_check(self):
        user = User.objects.create_user("staffuser", password="pass", is_staff=True)
        token = Token.objects.create(user=user)
        project = ProjectFactory()
        # No membership created — staff should still access

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(f"/v1/projects/{project.id}/workplans/")
        assert response.status_code == 200

    def test_project_list_still_accessible(self):
        """Listing all projects should still work for any authenticated user."""
        user = User.objects.create_user("anyuser", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/projects/")
        assert response.status_code == 200
