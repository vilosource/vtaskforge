"""Step 5: v2 Project serializer tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from prefs.models import ProjectMembership

    user = User.objects.create_user("projv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="V2Proj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user, project


class TestProjectV2:

    def test_v2_project_owner_is_actor_ref(self, setup):
        """DoD #1"""
        client, user, project = setup
        resp = client.get(f"/v2/projects/{project.id}/")
        assert resp.status_code == 200
        owner = resp.data["owner"]
        assert isinstance(owner, dict)
        assert owner["type"] == "user"
        assert owner["username"] == "projv2user"

    def test_v2_project_created_by_is_actor_ref(self, setup):
        """DoD #2"""
        client, user, project = setup
        resp = client.get(f"/v2/projects/{project.id}/")
        cb = resp.data["created_by"]
        assert isinstance(cb, dict)
        assert cb["type"] == "user"

    def test_v2_project_has_permissions(self, setup):
        """DoD #3"""
        client, user, project = setup
        resp = client.get(f"/v2/projects/{project.id}/")
        perms = resp.data["permissions"]
        assert "can_edit" in perms
        assert "can_delete" in perms
        assert "can_archive" in perms
        assert "can_manage_members" in perms

    def test_v1_project_unchanged(self, setup):
        """DoD #4"""
        client, user, project = setup
        resp = client.get(f"/v1/projects/{project.id}/")
        assert resp.status_code == 200
        # v1: owner is a username string, not a dict
        assert isinstance(resp.data["owner"], str)
        assert "permissions" not in resp.data

    def test_v2_project_create_returns_v2_shape(self, setup):
        """DoD #5"""
        client, user, project = setup
        resp = client.post("/v2/projects/", {"name": "NewProj"}, format="json")
        assert resp.status_code == 201
        assert isinstance(resp.data["owner"], dict)

    def test_v2_project_null_owner(self, setup):
        """DoD #6"""
        from projects.models import Project
        client, user, _ = setup
        project = Project.objects.create(name="NoOwner", owner=None, created_by=user)
        resp = client.get(f"/v2/projects/{project.id}/")
        assert resp.data["owner"] is None
