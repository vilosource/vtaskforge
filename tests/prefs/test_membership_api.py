"""TDD tests for project membership API endpoints.

Nested under /v1/projects/<project_id>/members/.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import ProjectMembership, UserProfile
from projects.models import Project


def _make_staff_client():
    user = User.objects.create_user("staff1", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    UserProfile.objects.create(user=user, user_type="human")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_member_client(project_id, role="member"):
    user = User.objects.create_user(f"member-{role}", password="pass")
    token = Token.objects.create(user=user)
    UserProfile.objects.create(user=user, user_type="human")
    ProjectMembership.objects.create(user=user, project_id=project_id, role=role)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_non_member_client():
    user = User.objects.create_user("outsider", password="pass")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


@pytest.fixture
def project(db):
    return Project.objects.create(id="test-proj", name="Test Project")


@pytest.mark.django_db
class TestListMembers:
    def test_staff_can_list(self, project):
        client, staff = _make_staff_client()
        user = User.objects.create_user("alice", password="pass")
        ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
        response = client.get(f"/v1/projects/{project.id}/members/")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["username"] == "alice"

    def test_member_can_list(self, project):
        client, _ = _make_member_client(project.id)
        response = client.get(f"/v1/projects/{project.id}/members/")
        assert response.status_code == 200

    def test_non_member_gets_403(self, project):
        client, _ = _make_non_member_client()
        response = client.get(f"/v1/projects/{project.id}/members/")
        assert response.status_code == 403

    def test_response_shape(self, project):
        client, _ = _make_staff_client()
        user = User.objects.create_user("alice", password="pass")
        ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
        response = client.get(f"/v1/projects/{project.id}/members/")
        member = response.json()["results"][0]
        assert "id" in member
        assert "user_id" in member
        assert "username" in member
        assert "role" in member
        assert "created_at" in member


@pytest.mark.django_db
class TestAddMember:
    def test_staff_can_add(self, project):
        client, _ = _make_staff_client()
        user = User.objects.create_user("alice", password="pass")
        response = client.post(
            f"/v1/projects/{project.id}/members/",
            {"username": "alice", "role": "member"},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["username"] == "alice"
        assert response.json()["role"] == "member"

    def test_non_staff_gets_403(self, project):
        client, _ = _make_member_client(project.id, role="owner")
        User.objects.create_user("alice", password="pass")
        response = client.post(
            f"/v1/projects/{project.id}/members/",
            {"username": "alice", "role": "member"},
            format="json",
        )
        assert response.status_code == 403

    def test_nonexistent_user_returns_400(self, project):
        client, _ = _make_staff_client()
        response = client.post(
            f"/v1/projects/{project.id}/members/",
            {"username": "ghost", "role": "member"},
            format="json",
        )
        assert response.status_code == 400

    def test_duplicate_member_returns_409(self, project):
        client, _ = _make_staff_client()
        user = User.objects.create_user("alice", password="pass")
        ProjectMembership.objects.create(user=user, project_id=project.id, role="member")
        response = client.post(
            f"/v1/projects/{project.id}/members/",
            {"username": "alice", "role": "viewer"},
            format="json",
        )
        assert response.status_code == 409

    def test_default_role_is_member(self, project):
        client, _ = _make_staff_client()
        User.objects.create_user("alice", password="pass")
        response = client.post(
            f"/v1/projects/{project.id}/members/",
            {"username": "alice"},
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["role"] == "member"


@pytest.mark.django_db
class TestUpdateMemberRole:
    def test_staff_can_change_role(self, project):
        client, _ = _make_staff_client()
        user = User.objects.create_user("alice", password="pass")
        m = ProjectMembership.objects.create(user=user, project_id=project.id, role="member")
        response = client.patch(
            f"/v1/projects/{project.id}/members/{m.pk}/",
            {"role": "owner"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["role"] == "owner"

    def test_non_staff_gets_403(self, project):
        client, _ = _make_member_client(project.id, role="owner")
        user = User.objects.create_user("alice", password="pass")
        m = ProjectMembership.objects.create(user=user, project_id=project.id, role="member")
        response = client.patch(
            f"/v1/projects/{project.id}/members/{m.pk}/",
            {"role": "owner"},
            format="json",
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestRemoveMember:
    def test_staff_can_remove(self, project):
        client, _ = _make_staff_client()
        user = User.objects.create_user("alice", password="pass")
        m = ProjectMembership.objects.create(user=user, project_id=project.id, role="member")
        response = client.delete(f"/v1/projects/{project.id}/members/{m.pk}/")
        assert response.status_code == 204
        assert not ProjectMembership.objects.filter(pk=m.pk).exists()

    def test_non_staff_gets_403(self, project):
        client, _ = _make_member_client(project.id, role="owner")
        user = User.objects.create_user("alice", password="pass")
        m = ProjectMembership.objects.create(user=user, project_id=project.id, role="member")
        response = client.delete(f"/v1/projects/{project.id}/members/{m.pk}/")
        assert response.status_code == 403

    def test_nonexistent_returns_404(self, project):
        client, _ = _make_staff_client()
        response = client.delete(f"/v1/projects/{project.id}/members/99999/")
        assert response.status_code == 404
