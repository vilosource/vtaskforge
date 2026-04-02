"""TDD tests for lock API endpoints.

Phase 3 of User Management: acquire/release/list locks.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import AgentLock


@pytest.mark.django_db
class TestLockAPI:
    def test_acquire_lock_returns_200(self):
        user = User.objects.create_user("user1", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
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
        u1 = User.objects.create_user("u1", password="pass")
        u2 = User.objects.create_user("u2", password="pass")
        t1 = Token.objects.create(user=u1)
        t2 = Token.objects.create(user=u2)

        c1 = APIClient()
        c1.credentials(HTTP_AUTHORIZATION=f"Token {t1.key}")
        c1.post("/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json")

        c2 = APIClient()
        c2.credentials(HTTP_AUTHORIZATION=f"Token {t2.key}")
        response = c2.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )

        assert response.status_code == 409
        assert "locked_by" in response.json()

    def test_acquire_own_lock_returns_existing(self):
        user = User.objects.create_user("user1", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
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
        user = User.objects.create_user("user1", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )
        lock_id = response.json()["id"]

        response = client.delete(f"/v1/locks/{lock_id}/")
        assert response.status_code == 200
        assert not AgentLock.objects.filter(pk=lock_id).exists()

    def test_list_locks_for_project(self):
        user = User.objects.create_user("user1", password="pass")
        token = Token.objects.create(user=user)
        AgentLock.objects.create(project_id="proj1", role="architect", user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/locks/", {"project_id": "proj1"})

        assert response.status_code == 200
        assert len(response.json()["results"]) == 1

    def test_lock_response_includes_holder_info(self):
        user = User.objects.create_user("admin", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(
            "/v1/locks/", {"project_id": "proj1", "role": "architect"}, format="json"
        )

        data = response.json()
        assert "id" in data
        assert "user" in data
        assert "created_at" in data
        assert data["user"] == "admin"
