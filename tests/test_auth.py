"""
Authentication integration tests.

Verifies that:
- Health endpoint is fully public (no auth required)
- Agent registration is public and returns a token
- All other endpoints require a valid Token
"""
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import WorkplanFactory


@pytest.mark.django_db
class TestHealthNoAuth:
    def test_health_without_auth_returns_200(self):
        """Health endpoint must be accessible without any credentials."""
        client = APIClient()
        response = client.get("/v1/health")
        # 200 when all services up, 503 when Redis unavailable — both are valid
        # (the point is it doesn't return 401/403)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@pytest.mark.django_db
class TestAgentRegistrationNoAuth:
    def test_register_without_auth_returns_201(self):
        """Agent registration must succeed without credentials."""
        client = APIClient()
        payload = {"name": "Unauthenticated Agent"}
        response = client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_register_returns_token(self):
        """Agent registration must return a token in the response body."""
        client = APIClient()
        payload = {"name": "Token Agent"}
        response = client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "token" in response.data
        assert len(response.data["token"]) == 40

    def test_register_token_can_authenticate_subsequent_requests(self):
        """Token returned at registration must work for subsequent authenticated calls."""
        client = APIClient()
        payload = {"name": "Auth-capable Agent"}
        response = client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        token = response.data["token"]

        # Use the token to call an authenticated endpoint
        client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        list_response = client.get("/v1/workplans/")
        assert list_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestWorkplansRequireAuth:
    def test_workplans_without_auth_returns_401(self):
        """Workplans list must reject unauthenticated requests."""
        client = APIClient()
        response = client.get("/v1/workplans/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_workplans_with_valid_token_returns_200(self, api_client):
        """Workplans list must succeed with a valid token."""
        response = api_client.get("/v1/workplans/")
        assert response.status_code == status.HTTP_200_OK

    def test_workplans_with_invalid_token_returns_401(self):
        """Workplans list must reject an invalid token."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token invalidtoken00000000000000000000000")
        response = client.get("/v1/workplans/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
