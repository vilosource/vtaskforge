"""TDD tests for lock permission fixes.

- POST /v1/locks/ should only work for agents + staff (not regular humans)
- DELETE /v1/locks/<pk>/ should work for owner OR staff (force-release)
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import AgentLock


def _make_human_client():
    """Regular human user with password."""
    user = User.objects.create_user("human1", password="pass")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_agent_client():
    """Agent user without password."""
    user = User.objects.create_user("agent1")  # no password = agent
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_staff_client():
    """Staff human user."""
    user = User.objects.create_user("staff1", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


@pytest.mark.django_db
class TestLockAcquirePermissions:
    def test_agent_can_acquire(self):
        client, _ = _make_agent_client()
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect"},
            format="json",
        )
        assert response.status_code == 200

    def test_staff_can_acquire(self):
        client, _ = _make_staff_client()
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect"},
            format="json",
        )
        assert response.status_code == 200

    def test_human_cannot_acquire(self):
        client, _ = _make_human_client()
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect"},
            format="json",
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestLockForceRelease:
    def test_owner_can_release(self):
        client, user = _make_agent_client()
        lock = AgentLock.objects.create(project_id="proj1", role="architect", user=user)
        response = client.delete(f"/v1/locks/{lock.pk}/")
        assert response.status_code == 200
        assert not AgentLock.objects.filter(pk=lock.pk).exists()

    def test_staff_can_force_release(self):
        agent_user = User.objects.create_user("agent-x")
        lock = AgentLock.objects.create(project_id="proj1", role="architect", user=agent_user)
        staff_client, _ = _make_staff_client()
        response = staff_client.delete(f"/v1/locks/{lock.pk}/")
        assert response.status_code == 200
        assert not AgentLock.objects.filter(pk=lock.pk).exists()

    def test_other_agent_cannot_release(self):
        agent_owner = User.objects.create_user("agent-owner")
        lock = AgentLock.objects.create(project_id="proj1", role="architect", user=agent_owner)
        client, _ = _make_agent_client()  # different agent
        response = client.delete(f"/v1/locks/{lock.pk}/")
        assert response.status_code == 404  # not found (not their lock, not staff)


@pytest.mark.django_db
class TestLockUserIdProxy:
    """R8: Agent/staff can create locks on behalf of another user."""

    def test_agent_creates_lock_with_user_id_proxy(self):
        """POST /v1/locks/ with user_id creates lock owned by target user."""
        client, _ = _make_agent_client()
        target = User.objects.create_user("target-human", password="pass")
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect", "user_id": target.pk},
            format="json",
        )
        assert response.status_code == 200
        lock = AgentLock.objects.get(project_id="proj1", role="architect")
        assert lock.user == target
        assert response.data["user"] == "target-human"
        assert response.data["user_id"] == target.pk

    def test_staff_creates_lock_with_user_id_proxy(self):
        """Staff can also proxy lock creation."""
        client, _ = _make_staff_client()
        target = User.objects.create_user("target-user2", password="pass")
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect", "user_id": target.pk},
            format="json",
        )
        assert response.status_code == 200
        lock = AgentLock.objects.get(project_id="proj1", role="architect")
        assert lock.user == target

    def test_lock_without_user_id_uses_request_user(self):
        """Without user_id, lock is created for the authenticated user (existing behavior)."""
        client, agent_user = _make_agent_client()
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect"},
            format="json",
        )
        assert response.status_code == 200
        lock = AgentLock.objects.get(project_id="proj1", role="architect")
        assert lock.user == agent_user

    def test_lock_with_invalid_user_id_returns_400(self):
        """POST with non-existent user_id returns 400."""
        client, _ = _make_agent_client()
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect", "user_id": 99999},
            format="json",
        )
        assert response.status_code == 400
        assert "not found" in response.data["detail"]

    def test_lock_serializer_includes_user_id(self):
        """AgentLockSerializer returns user_id in response."""
        client, _ = _make_agent_client()
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect"},
            format="json",
        )
        assert response.status_code == 200
        assert "user_id" in response.data
