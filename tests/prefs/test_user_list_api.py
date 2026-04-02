"""TDD tests for user list/detail/update API endpoints.

Staff-only endpoints for user management.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import UserProfile, ProjectMembership


def _make_staff_client():
    user = User.objects.create_user("staff1", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    UserProfile.objects.create(user=user, user_type="human")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_regular_client():
    user = User.objects.create_user("regular1", password="pass")
    token = Token.objects.create(user=user)
    UserProfile.objects.create(user=user, user_type="human")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_user(username, user_type="human", is_staff=False):
    user = User.objects.create_user(username, password="pass", is_staff=is_staff)
    UserProfile.objects.create(user=user, user_type=user_type)
    return user


@pytest.mark.django_db
class TestUserListAPI:
    def test_staff_can_list_users(self):
        client, _ = _make_staff_client()
        _make_user("alice")
        _make_user("bob")
        response = client.get("/v1/users/")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        # Staff user + alice + bob = at least 3
        assert len(data["results"]) >= 3

    def test_non_staff_gets_403(self):
        client, _ = _make_regular_client()
        response = client.get("/v1/users/")
        assert response.status_code == 403

    def test_unauthenticated_gets_401(self):
        client = APIClient()
        response = client.get("/v1/users/")
        assert response.status_code in (401, 403)

    def test_search_by_username(self):
        client, _ = _make_staff_client()
        _make_user("alice")
        _make_user("bob")
        response = client.get("/v1/users/", {"search": "ali"})
        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["username"] == "alice"

    def test_filter_by_user_type(self):
        client, _ = _make_staff_client()
        _make_user("alice", user_type="human")
        _make_user("bot1", user_type="agent")
        response = client.get("/v1/users/", {"user_type": "agent"})
        assert response.status_code == 200
        results = response.json()["results"]
        assert all(r["user_type"] == "agent" for r in results)

    def test_response_includes_user_type(self):
        client, _ = _make_staff_client()
        _make_user("alice", user_type="human")
        response = client.get("/v1/users/", {"search": "alice"})
        assert response.status_code == 200
        user_data = response.json()["results"][0]
        assert "user_type" in user_data
        assert user_data["user_type"] == "human"


@pytest.mark.django_db
class TestUserDetailAPI:
    def test_staff_can_get_detail(self):
        client, _ = _make_staff_client()
        user = _make_user("alice")
        response = client.get(f"/v1/users/{user.pk}/")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "alice"
        assert "memberships" in data

    def test_detail_includes_memberships(self):
        client, _ = _make_staff_client()
        user = _make_user("alice")
        ProjectMembership.objects.create(user=user, project_id="proj1", role="owner")
        response = client.get(f"/v1/users/{user.pk}/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["memberships"]) == 1
        assert data["memberships"][0]["role"] == "owner"

    def test_non_staff_gets_403(self):
        client, _ = _make_regular_client()
        user = _make_user("alice")
        response = client.get(f"/v1/users/{user.pk}/")
        assert response.status_code == 403

    def test_not_found_returns_404(self):
        client, _ = _make_staff_client()
        response = client.get("/v1/users/99999/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestUserUpdateAPI:
    def test_staff_can_update_user_type(self):
        client, _ = _make_staff_client()
        user = _make_user("alice", user_type="human")
        response = client.patch(
            f"/v1/users/{user.pk}/",
            {"user_type": "service"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json()["user_type"] == "service"

    def test_invalid_user_type_returns_400(self):
        client, _ = _make_staff_client()
        user = _make_user("alice")
        response = client.patch(
            f"/v1/users/{user.pk}/",
            {"user_type": "invalid"},
            format="json",
        )
        assert response.status_code == 400

    def test_non_staff_gets_403(self):
        client, _ = _make_regular_client()
        user = _make_user("alice")
        response = client.patch(
            f"/v1/users/{user.pk}/",
            {"user_type": "service"},
            format="json",
        )
        assert response.status_code == 403
