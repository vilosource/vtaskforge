"""TDD tests for GET /v1/auth/validate/ — token validation endpoint.

Phase 1 of User Management: cross-service token validation API.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import UserProfile


@pytest.mark.django_db
class TestTokenValidationEndpoint:
    def test_validate_human_token_returns_correct_payload(self):
        user = User.objects.create_user("admin", password="pass", is_staff=True)
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/auth/validate/")

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user.pk
        assert data["username"] == "admin"
        assert data["user_type"] == "human"
        assert data["is_staff"] is True

    def test_validate_agent_token_returns_agent_type(self):
        user = User.objects.create_user("executor-1")  # No password = agent
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/auth/validate/")

        assert response.status_code == 200
        data = response.json()
        assert data["user_type"] == "agent"
        assert data["is_staff"] is False

    def test_validate_invalid_token_returns_401(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token invalidgarbage123")
        response = client.get("/v1/auth/validate/")
        assert response.status_code == 401

    def test_validate_no_token_returns_401(self):
        client = APIClient()
        response = client.get("/v1/auth/validate/")
        assert response.status_code == 401

    def test_validate_response_includes_user_id_username_type_staff(self):
        user = User.objects.create_user("checker", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/auth/validate/")

        data = response.json()
        assert "user_id" in data
        assert "username" in data
        assert "user_type" in data
        assert "is_staff" in data
        assert "projects" in data

    def test_validate_projects_is_empty_list(self):
        """Phase 1: projects is always empty (populated in Phase 4)."""
        user = User.objects.create_user("proj1", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/auth/validate/")

        assert response.json()["projects"] == []

    def test_validate_auto_creates_profile(self):
        """Validation should auto-create UserProfile if it doesn't exist."""
        user = User.objects.create_user("noprofile", password="pass")
        assert not UserProfile.objects.filter(user=user).exists()

        token = Token.objects.create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/auth/validate/")

        assert response.status_code == 200
        assert UserProfile.objects.filter(user=user).exists()

    def test_validate_with_session_auth(self):
        """Session auth should also work for validate endpoint."""
        user = User.objects.create_user("session1", password="pass")

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/v1/auth/validate/")

        assert response.status_code == 200
        assert response.json()["username"] == "session1"
