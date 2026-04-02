"""TDD tests for service account creation.

Phase 5 of User Management: service accounts for automated services.
"""

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import UserProfile
from prefs.services import create_service_account


@pytest.mark.django_db
class TestServiceAccounts:
    def test_create_service_account(self):
        user, token = create_service_account("summarizer")
        assert user.username == "summarizer"
        assert token.key is not None

    def test_service_account_has_user_type_service(self):
        user, _ = create_service_account("summarizer")
        profile = UserProfile.objects.get(user=user)
        assert profile.user_type == "service"

    def test_validate_returns_service_type(self):
        user, token = create_service_account("summarizer")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/auth/validate/")

        assert response.status_code == 200
        assert response.json()["user_type"] == "service"

    def test_service_account_has_no_usable_password(self):
        user, _ = create_service_account("summarizer")
        assert not user.has_usable_password()

    def test_create_service_account_command(self, capsys):
        call_command("create_service_account", "auto-discovery")
        output = capsys.readouterr().out
        assert "auto-discovery" in output
        assert User.objects.filter(username="auto-discovery").exists()
        token = Token.objects.get(user__username="auto-discovery")
        assert token.key in output
