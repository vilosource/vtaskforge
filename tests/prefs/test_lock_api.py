"""TDD tests for lock API endpoints.

Phase 3 of User Management: acquire/release/list locks.
Updated: lock acquire now requires agent or staff users.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import AgentLock


def _make_agent_client(username="agent1"):
    """Create an agent user (no password) with token."""
    user = User.objects.create_user(username)  # no password = agent
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


@pytest.mark.django_db
class TestLockAPI:
    def test_acquire_lock_returns_200(self):
        client, user = _make_agent_client()
        response = client.post(
            "/v1/locks/",
            {"project_id": "proj1", "role": "architect"},
            format="json",
        )

        assert response.status_code == 200
        assert AgentLock.objects.filter(
            project_id="proj1", role="architect", user=user
        ).exists()

    def test_acquire_locked_by_other_returns_409(self):
        c1, _ = _make_agent_client("agent-a")
        c1.post("/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json")

        c2, _ = _make_agent_client("agent-b")
        response = c2.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )

        assert response.status_code == 409
        assert "locked_by" in response.json()

    def test_acquire_own_lock_returns_existing(self):
        client, _ = _make_agent_client()
        r1 = client.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )
        r2 = client.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    def test_release_lock(self):
        client, _ = _make_agent_client()
        response = client.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )
        lock_id = response.json()["id"]

        response = client.delete(f"/v1/locks/{lock_id}/")
        assert response.status_code == 200
        assert not AgentLock.objects.filter(pk=lock_id).exists()

    def test_list_locks_for_project(self):
        client, user = _make_agent_client()
        AgentLock.objects.create(project_id="proj1", role="architect", user=user)

        response = client.get("/v1/locks/", {"project_id": "proj1"})

        assert response.status_code == 200
        assert len(response.json()["results"]) == 1

    def test_lock_response_includes_holder_info(self):
        client, _ = _make_agent_client("my-agent")
        response = client.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )

        data = response.json()
        assert "id" in data
        assert "user" in data
        assert "created_at" in data
        assert data["user"] == "my-agent"

    def test_patch_lock_updates_session_id(self):
        client, user = _make_agent_client()
        lock = AgentLock.objects.create(
            project_id="proj1", role="architect", user=user, session_id=""
        )

        response = client.patch(
            f"/v1/locks/{lock.pk}/",
            {"session_id": "real-sess-123"},
            format="json",
        )

        assert response.status_code == 200
        lock.refresh_from_db()
        assert lock.session_id == "real-sess-123"

    def test_patch_lock_returns_404_for_missing(self):
        client, _ = _make_agent_client()
        response = client.patch(
            "/v1/locks/99999/",
            {"session_id": "x"},
            format="json",
        )
        assert response.status_code == 404
