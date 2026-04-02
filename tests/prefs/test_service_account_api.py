"""TDD tests for service account creation API.

POST /v1/service-accounts/ — staff-only.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import UserProfile


def _make_staff_client():
    user = User.objects.create_user("staff1", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


def _make_regular_client():
    user = User.objects.create_user("regular1", password="pass")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.mark.django_db
class TestServiceAccountAPI:
    def test_staff_can_create(self):
        client = _make_staff_client()
        response = client.post(
            "/v1/service-accounts/",
            {"name": "ci-bot"},
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "ci-bot"
        assert "token" in data
        assert len(data["token"]) == 40  # DRF token length
        assert data["user_type"] == "service"

    def test_non_staff_gets_403(self):
        client = _make_regular_client()
        response = client.post(
            "/v1/service-accounts/",
            {"name": "ci-bot"},
            format="json",
        )
        assert response.status_code == 403

    def test_duplicate_name_returns_400(self):
        client = _make_staff_client()
        client.post("/v1/service-accounts/", {"name": "ci-bot"}, format="json")
        response = client.post(
            "/v1/service-accounts/",
            {"name": "ci-bot"},
            format="json",
        )
        assert response.status_code == 400

    def test_missing_name_returns_400(self):
        client = _make_staff_client()
        response = client.post("/v1/service-accounts/", {}, format="json")
        assert response.status_code == 400

    def test_created_user_has_no_password(self):
        client = _make_staff_client()
        client.post("/v1/service-accounts/", {"name": "ci-bot"}, format="json")
        user = User.objects.get(username="ci-bot")
        assert not user.has_usable_password()

    def test_created_user_has_service_profile(self):
        client = _make_staff_client()
        client.post("/v1/service-accounts/", {"name": "ci-bot"}, format="json")
        profile = UserProfile.objects.get(user__username="ci-bot")
        assert profile.user_type == "service"
