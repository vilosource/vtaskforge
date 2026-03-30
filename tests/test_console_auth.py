"""
Console auth integration tests — TDD RED phase.

Tests for the authorization code flow used by vafi-console:
- ConsoleAuthCode model (single-use, 60s expiry)
- POST /v1/auth/code/ (generate code, requires auth)
- POST /v1/auth/exchange/ (exchange code for user info, no auth)
- GET /auth/console-login/?next=URL (redirect flow)
"""

import time

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.models import ConsoleAuthCode


@pytest.mark.django_db
class TestConsoleAuthCodeModel:
    def test_create_code(self):
        user = User.objects.create_user(username="testuser", password="testpass")
        code = ConsoleAuthCode.objects.create_code(
            user=user,
            redirect_uri="https://console.dev.viloforge.com/?role=architect",
        )
        assert len(code.code) >= 32
        assert code.user == user
        assert code.used is False
        assert code.redirect_uri == "https://console.dev.viloforge.com/?role=architect"

    def test_code_is_unique(self):
        user = User.objects.create_user(username="testuser", password="testpass")
        codes = set()
        for _ in range(50):
            c = ConsoleAuthCode.objects.create_code(user=user, redirect_uri="https://example.com")
            codes.add(c.code)
        assert len(codes) == 50

    def test_code_has_expiry(self):
        user = User.objects.create_user(username="testuser", password="testpass")
        code = ConsoleAuthCode.objects.create_code(user=user, redirect_uri="https://example.com")
        assert code.expires_at > timezone.now()
        # Should expire within ~60 seconds
        delta = (code.expires_at - timezone.now()).total_seconds()
        assert 55 <= delta <= 65

    def test_validate_valid_code(self):
        user = User.objects.create_user(username="testuser", password="testpass")
        code = ConsoleAuthCode.objects.create_code(user=user, redirect_uri="https://example.com")
        result = ConsoleAuthCode.objects.validate_code(code.code)
        assert result is not None
        assert result.user == user
        # Code should be marked as used
        code.refresh_from_db()
        assert code.used is True

    def test_validate_used_code_fails(self):
        user = User.objects.create_user(username="testuser", password="testpass")
        code = ConsoleAuthCode.objects.create_code(user=user, redirect_uri="https://example.com")
        # Use it once
        ConsoleAuthCode.objects.validate_code(code.code)
        # Second use should fail
        result = ConsoleAuthCode.objects.validate_code(code.code)
        assert result is None

    def test_validate_nonexistent_code_fails(self):
        result = ConsoleAuthCode.objects.validate_code("nonexistent-code")
        assert result is None

    def test_validate_expired_code_fails(self):
        user = User.objects.create_user(username="testuser", password="testpass")
        code = ConsoleAuthCode.objects.create_code(user=user, redirect_uri="https://example.com")
        # Force expire
        code.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        code.save()
        result = ConsoleAuthCode.objects.validate_code(code.code)
        assert result is None


@pytest.mark.django_db
class TestCodeGenerationEndpoint:
    def test_generate_code_authenticated(self, api_client):
        """Authenticated user can generate a code."""
        resp = api_client.post("/v1/auth/code/", {
            "redirect_uri": "https://console.dev.viloforge.com/?role=architect",
        }, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert "code" in resp.data
        assert "expires_at" in resp.data
        assert len(resp.data["code"]) >= 32

    def test_generate_code_unauthenticated(self):
        """Unauthenticated request is rejected."""
        client = APIClient()
        resp = client.post("/v1/auth/code/", {
            "redirect_uri": "https://console.dev.viloforge.com/",
        }, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_generate_code_requires_redirect_uri(self, api_client):
        """redirect_uri is required."""
        resp = api_client.post("/v1/auth/code/", {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestCodeExchangeEndpoint:
    def test_exchange_valid_code(self):
        """Valid code returns user info."""
        user = User.objects.create_user(
            username="jason", password="testpass", is_staff=True,
        )
        code = ConsoleAuthCode.objects.create_code(
            user=user, redirect_uri="https://console.dev.viloforge.com/",
        )
        client = APIClient()
        resp = client.post("/v1/auth/exchange/", {
            "code": code.code,
        }, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["user_id"] == user.id
        assert resp.data["username"] == "jason"
        assert resp.data["is_staff"] is True

    def test_exchange_invalid_code(self):
        """Invalid code returns 400."""
        client = APIClient()
        resp = client.post("/v1/auth/exchange/", {
            "code": "invalid-code",
        }, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_exchange_used_code(self):
        """Already-used code returns 400."""
        user = User.objects.create_user(username="jason", password="testpass")
        code = ConsoleAuthCode.objects.create_code(
            user=user, redirect_uri="https://console.dev.viloforge.com/",
        )
        client = APIClient()
        # First exchange succeeds
        resp1 = client.post("/v1/auth/exchange/", {"code": code.code}, format="json")
        assert resp1.status_code == status.HTTP_200_OK
        # Second exchange fails
        resp2 = client.post("/v1/auth/exchange/", {"code": code.code}, format="json")
        assert resp2.status_code == status.HTTP_400_BAD_REQUEST

    def test_exchange_does_not_require_auth(self):
        """Exchange endpoint is public (the code IS the auth)."""
        user = User.objects.create_user(username="jason", password="testpass")
        code = ConsoleAuthCode.objects.create_code(
            user=user, redirect_uri="https://console.dev.viloforge.com/",
        )
        client = APIClient()  # no credentials
        resp = client.post("/v1/auth/exchange/", {"code": code.code}, format="json")
        assert resp.status_code == status.HTTP_200_OK

    def test_exchange_requires_code_field(self):
        """Missing code field returns 400."""
        client = APIClient()
        resp = client.post("/v1/auth/exchange/", {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestConsoleLoginRedirect:
    def test_authenticated_user_redirects_with_code(self):
        """Authenticated user is redirected to console with a code."""
        client = APIClient()
        user = User.objects.create_user(username="jason", password="testpass")
        client.login(username="jason", password="testpass")
        resp = client.get(
            "/auth/console-login/",
            {"next": "https://console.dev.viloforge.com/?role=architect"},
        )
        assert resp.status_code == 302
        assert "console.dev.viloforge.com" in resp.url
        assert "code=" in resp.url

    def test_unauthenticated_user_redirects_to_login(self):
        """Unauthenticated user is redirected to Django login."""
        client = APIClient()
        resp = client.get(
            "/auth/console-login/",
            {"next": "https://console.dev.viloforge.com/"},
        )
        assert resp.status_code == 302
        # Should redirect to Django login page (not directly to console)
        assert "/login/" in resp.url
        # The console URL should be in the nested next param (so after login,
        # Django redirects back to console-login, which then redirects to console)
        assert "code=" not in resp.url
