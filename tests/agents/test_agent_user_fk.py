"""TDD tests for Agent.user OneToOneField (Phase 0, Step 1).

Tests that every Agent is explicitly linked to a Django User via FK,
replacing the implicit convention of User.username == Agent.id.

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Step 1 DoD.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from agents.models import Agent
from tests.factories import AgentFactory


@pytest.mark.django_db
class TestAgentUserLinkedOnCreate:
    """POST /v1/agents/ must create Agent with user FK set."""

    def test_agent_create_links_user(self):
        """New agent registration creates a User and links it via FK."""
        client = APIClient()
        payload = {"name": "executor-1", "tags": ["executor"]}
        response = client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        agent = Agent.objects.get(id=response.data["id"])
        assert agent.user is not None
        assert agent.user.username == agent.id

    def test_agent_upsert_preserves_user(self):
        """Re-registering an existing agent preserves the User FK."""
        client = APIClient()
        payload = {"name": "executor-1", "tags": ["executor"]}

        # First registration
        r1 = client.post("/v1/agents/", payload, format="json")
        assert r1.status_code == status.HTTP_201_CREATED
        agent_id = r1.data["id"]
        first_token = r1.data["token"]

        agent = Agent.objects.get(id=agent_id)
        first_user_id = agent.user.id

        # Second registration (upsert)
        r2 = client.post("/v1/agents/", payload, format="json")
        assert r2.status_code == status.HTTP_200_OK

        agent.refresh_from_db()
        assert agent.user.id == first_user_id  # Same user, not a new one
        assert r2.data["token"] == first_token  # Same token

        # No orphan users created
        user_count = User.objects.filter(username=agent_id).count()
        assert user_count == 1


@pytest.mark.django_db
class TestAgentUserReverseLookup:
    """User.agent reverse relation works via OneToOneField."""

    def test_agent_user_reverse_lookup(self):
        """user.agent returns the Agent instance."""
        client = APIClient()
        payload = {"name": "executor-2", "tags": []}
        response = client.post("/v1/agents/", payload, format="json")
        agent = Agent.objects.get(id=response.data["id"])

        user = agent.user
        assert user.agent == agent
        assert user.agent.name == "executor-2"


@pytest.mark.django_db
class TestAgentUserCascade:
    """Deleting a User cascades to its Agent (CASCADE)."""

    def test_agent_user_cascade_delete(self):
        """Deleting the User also deletes the Agent."""
        client = APIClient()
        payload = {"name": "executor-3", "tags": []}
        response = client.post("/v1/agents/", payload, format="json")
        agent_id = response.data["id"]

        agent = Agent.objects.get(id=agent_id)
        user = agent.user
        user.delete()

        assert not Agent.objects.filter(id=agent_id).exists()


@pytest.mark.django_db
class TestAgentWithoutUser:
    """Agent.user is nullable for pre-provisioned agents."""

    def test_agent_without_user_allowed(self):
        """An Agent can exist with user=None (pre-provisioned, not yet authenticated)."""
        agent = Agent.objects.create(
            name="pre-provisioned-agent",
            tags=["executor"],
            status="offline",
        )
        assert agent.user is None
        agent.full_clean()  # No validation error


@pytest.mark.django_db
class TestAgentFactoryUpdated:
    """AgentFactory creates agents with user FK set."""

    def test_factory_creates_user(self):
        """AgentFactory post-generation creates and links a User."""
        agent = AgentFactory(name="factory-agent")
        assert agent.user is not None
        assert agent.user.username == agent.id
