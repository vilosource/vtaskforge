"""TDD tests for channel mapping API endpoints.

Phase 3 of User Management: channel-to-project mapping CRUD.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import ChannelProjectMapping


@pytest.mark.django_db
class TestChannelMappingAPI:
    def test_create_mapping(self):
        user = User.objects.create_user("admin", password="pass", is_staff=True)
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(
            "/v1/channel-mappings/",
            {"provider": "slack", "channel_id": "C123", "channel_name": "#vtf-dev", "project_id": "proj1"},
            format="json",
        )

        assert response.status_code == 201
        assert ChannelProjectMapping.objects.filter(channel_id="C123").exists()

    def test_list_mappings(self):
        user = User.objects.create_user("admin", password="pass", is_staff=True)
        token = Token.objects.create(user=user)
        ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", project_id="proj1"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/channel-mappings/")

        assert response.status_code == 200
        assert len(response.json()["results"]) == 1

    def test_lookup_by_channel(self):
        user = User.objects.create_user("admin", password="pass", is_staff=True)
        token = Token.objects.create(user=user)
        ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C999", project_id="my-project"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get(
            "/v1/channel-mappings/", {"provider": "slack", "channel_id": "C999"}
        )

        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["project_id"] == "my-project"

    def test_delete_mapping(self):
        user = User.objects.create_user("admin", password="pass", is_staff=True)
        token = Token.objects.create(user=user)
        mapping = ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", project_id="proj1"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.delete(f"/v1/channel-mappings/{mapping.pk}/")

        assert response.status_code == 204
        assert not ChannelProjectMapping.objects.filter(pk=mapping.pk).exists()
