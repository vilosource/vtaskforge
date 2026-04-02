"""TDD tests for session record write API.

POST /v1/sessions/ — create session records (service accounts, agents, staff).
Supports proxy mode: caller passes user_id to record on behalf of another user.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import SessionRecord, UserProfile


def _make_service_client():
    user = User.objects.create_user("bridge-svc")
    Token.objects.create(user=user)
    UserProfile.objects.create(user=user, user_type="service")
    token = Token.objects.get(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_staff_client():
    user = User.objects.create_user("staff1", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


def _make_human_client():
    user = User.objects.create_user("human1", password="pass")
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user


@pytest.mark.django_db
class TestSessionRecordCreate:
    def test_service_account_can_create(self):
        client, svc_user = _make_service_client()
        response = client.post(
            "/v1/sessions/",
            {
                "project_id": "proj1",
                "role": "architect",
                "channel": "web",
                "cxdb_context_id": 42,
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == "proj1"
        assert data["role"] == "architect"
        assert data["channel"] == "web"
        assert data["cxdb_context_id"] == 42
        assert SessionRecord.objects.filter(user=svc_user, project_id="proj1").exists()

    def test_staff_can_create(self):
        client, staff = _make_staff_client()
        response = client.post(
            "/v1/sessions/",
            {"project_id": "proj1", "role": "executor", "channel": "slack"},
            format="json",
        )
        assert response.status_code == 201

    def test_human_cannot_create(self):
        client, _ = _make_human_client()
        response = client.post(
            "/v1/sessions/",
            {"project_id": "proj1", "role": "architect"},
            format="json",
        )
        assert response.status_code == 403

    def test_proxy_mode_with_user_id(self):
        """Service account creates record on behalf of another user."""
        client, _ = _make_service_client()
        target_user = User.objects.create_user("alice", password="pass")
        response = client.post(
            "/v1/sessions/",
            {
                "project_id": "proj1",
                "role": "architect",
                "channel": "web",
                "user_id": target_user.pk,
            },
            format="json",
        )
        assert response.status_code == 201
        record = SessionRecord.objects.get(project_id="proj1", role="architect")
        assert record.user == target_user

    def test_proxy_invalid_user_id_returns_400(self):
        client, _ = _make_service_client()
        response = client.post(
            "/v1/sessions/",
            {
                "project_id": "proj1",
                "role": "architect",
                "user_id": 99999,
            },
            format="json",
        )
        assert response.status_code == 400

    def test_defaults_to_request_user_without_user_id(self):
        client, svc_user = _make_service_client()
        response = client.post(
            "/v1/sessions/",
            {"project_id": "proj1", "role": "executor"},
            format="json",
        )
        assert response.status_code == 201
        record = SessionRecord.objects.get(project_id="proj1", role="executor")
        assert record.user == svc_user

    def test_missing_required_fields_returns_400(self):
        client, _ = _make_service_client()
        response = client.post("/v1/sessions/", {}, format="json")
        assert response.status_code == 400

    def test_optional_fields(self):
        client, _ = _make_service_client()
        response = client.post(
            "/v1/sessions/",
            {
                "project_id": "proj1",
                "role": "architect",
                "channel": "slack",
                "summary": "Discussed architecture options",
                "ended_at": "2026-04-02T10:30:00Z",
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["summary"] == "Discussed architecture options"
        assert data["ended_at"] is not None

    def test_get_still_works_for_humans(self):
        """Existing read endpoint unchanged — humans can still list their sessions."""
        client, user = _make_human_client()
        SessionRecord.objects.create(user=user, project_id="proj1", role="architect")
        response = client.get("/v1/profile/sessions/")
        assert response.status_code == 200
        assert len(response.json()["results"]) == 1
