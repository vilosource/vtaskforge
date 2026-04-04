"""Step 10: Location header tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from prefs.models import ProjectMembership

    user = User.objects.create_user("locuser", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="LocProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, project


class TestLocationHeader:

    def test_location_header_v2_create(self, setup):
        """DoD #12: POST /v2/tasks/ → 201 with Location header."""
        client, project = setup
        resp = client.post("/v2/tasks/", {"title": "LocTask", "project": project.id}, format="json")
        assert resp.status_code == 201
        assert "Location" in resp
        assert resp["Location"].startswith("/v2/tasks/")

    def test_location_header_v2_project_create(self, setup):
        """DoD #13: POST /v2/projects/ → 201 with Location header."""
        client, _ = setup
        resp = client.post("/v2/projects/", {"name": "LocProj2"}, format="json")
        assert resp.status_code == 201
        assert "Location" in resp
        assert resp["Location"].startswith("/v2/projects/")

    def test_location_header_v1_no_change(self, setup):
        """DoD #14: POST /v1/tasks/ → 201 without Location header."""
        client, project = setup
        resp = client.post("/v1/tasks/", {"title": "V1LocTask", "project": project.id}, format="json")
        assert resp.status_code == 201
        assert "Location" not in resp
