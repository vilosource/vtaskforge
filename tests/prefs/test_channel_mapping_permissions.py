"""TDD tests for channel mapping permission fixes.

- POST /v1/channel-mappings/ should require staff
- DELETE /v1/channel-mappings/<pk>/ should require staff
- GET /v1/channel-mappings/ stays IsAuthenticated (agents need read for resolution)
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import ChannelProjectMapping


def _make_staff_client():
    user = User.objects.create_user("staff1", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


def _make_agent_client():
    user = User.objects.create_user("agent1")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


def _make_human_client():
    user = User.objects.create_user("human1", password="pass")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.mark.django_db
class TestChannelMappingReadPermissions:
    def test_agent_can_read(self):
        client = _make_agent_client()
        response = client.get("/v1/channel-mappings/")
        assert response.status_code == 200

    def test_human_can_read(self):
        client = _make_human_client()
        response = client.get("/v1/channel-mappings/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestChannelMappingWritePermissions:
    def test_staff_can_create(self):
        client = _make_staff_client()
        response = client.post(
            "/v1/channel-mappings/",
            {"provider": "slack", "channel_id": "C123", "project_id": "proj1"},
            format="json",
        )
        assert response.status_code == 201

    def test_non_staff_cannot_create(self):
        client = _make_human_client()
        response = client.post(
            "/v1/channel-mappings/",
            {"provider": "slack", "channel_id": "C123", "project_id": "proj1"},
            format="json",
        )
        assert response.status_code == 403

    def test_agent_cannot_create(self):
        client = _make_agent_client()
        response = client.post(
            "/v1/channel-mappings/",
            {"provider": "slack", "channel_id": "C123", "project_id": "proj1"},
            format="json",
        )
        assert response.status_code == 403


@pytest.mark.django_db
class TestChannelMappingDeletePermissions:
    def test_staff_can_delete(self):
        client = _make_staff_client()
        mapping = ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", project_id="proj1"
        )
        response = client.delete(f"/v1/channel-mappings/{mapping.pk}/")
        assert response.status_code == 204

    def test_non_staff_cannot_delete(self):
        client = _make_human_client()
        mapping = ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", project_id="proj1"
        )
        response = client.delete(f"/v1/channel-mappings/{mapping.pk}/")
        assert response.status_code == 403
