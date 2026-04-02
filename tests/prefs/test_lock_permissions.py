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
