"""TDD tests for ExternalIdentity API endpoints.

Phase 2 of User Management: identity management API.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import ExternalIdentity


@pytest.mark.django_db
class TestExternalIdentityAPI:
    def test_list_identities_for_current_user(self):
        user = User.objects.create_user("human1", password="pass")
        token = Token.objects.create(user=user)
        ExternalIdentity.objects.create(
            user=user, provider="slack", external_id="U111"
        )
        ExternalIdentity.objects.create(
            user=user, provider="whatsapp", external_id="+358123"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/external-identities/")

        assert response.status_code == 200
        assert len(response.json()["results"]) == 2

    def test_create_identity(self):
        user = User.objects.create_user("human2", password="pass")
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(
            "/v1/external-identities/",
            {"provider": "slack", "external_id": "U12345"},
            format="json",
        )

        assert response.status_code == 201
        assert ExternalIdentity.objects.filter(user=user, provider="slack").exists()

    def test_delete_identity(self):
        user = User.objects.create_user("human3", password="pass")
        token = Token.objects.create(user=user)
        identity = ExternalIdentity.objects.create(
            user=user, provider="slack", external_id="U333"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.delete(f"/v1/external-identities/{identity.pk}/")

        assert response.status_code == 204
        assert not ExternalIdentity.objects.filter(pk=identity.pk).exists()

    def test_lookup_identity_by_provider_external_id(self):
        user = User.objects.create_user("human4", password="pass")
        token = Token.objects.create(user=user)
        ExternalIdentity.objects.create(
            user=user, provider="slack", external_id="U444"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(
            "/v1/external-identities/", {"provider": "slack", "external_id": "U444"}
        )

        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["external_id"] == "U444"

    def test_agents_cannot_manage_identities(self):
        user = User.objects.create_user("agent1")  # No password = agent
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/external-identities/")

        assert response.status_code == 403
