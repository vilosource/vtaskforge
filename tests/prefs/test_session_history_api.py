"""TDD tests for session history API.

Phase 2 of User Management: read-only session listing for humans.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from prefs.models import SessionRecord


@pytest.mark.django_db
class TestSessionHistoryAPI:
    def test_list_sessions_for_current_user(self):
        user = User.objects.create_user("human1", password="pass")
        token = Token.objects.create(user=user)
        SessionRecord.objects.create(
            user=user, project_id="p1", role="architect", channel="web"
        )
        SessionRecord.objects.create(
            user=user, project_id="p2", role="assistant", channel="slack"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/profile/sessions/")

        assert response.status_code == 200
        assert len(response.json()["results"]) == 2

    def test_sessions_ordered_most_recent_first(self):
        user = User.objects.create_user("human2", password="pass")
        token = Token.objects.create(user=user)
        SessionRecord.objects.create(
            user=user, project_id="p1", role="architect"
        )
        SessionRecord.objects.create(
            user=user, project_id="p2", role="assistant"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/profile/sessions/")

        results = response.json()["results"]
        assert results[0]["project_id"] == "p2"
        assert results[1]["project_id"] == "p1"

    def test_filter_sessions_by_project(self):
        user = User.objects.create_user("human3", password="pass")
        token = Token.objects.create(user=user)
        SessionRecord.objects.create(
            user=user, project_id="proj-a", role="architect"
        )
        SessionRecord.objects.create(
            user=user, project_id="proj-b", role="assistant"
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/profile/sessions/", {"project": "proj-a"})

        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["project_id"] == "proj-a"

    def test_agents_cannot_list_sessions(self):
        user = User.objects.create_user("agent1")  # No password = agent
        token = Token.objects.create(user=user)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/profile/sessions/")

        assert response.status_code == 403
