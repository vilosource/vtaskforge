"""
Tests for Agent.pod_name field and its exposure through the API.
"""
import pytest
from rest_framework import status

from agents.models import Agent
from agents.serializers import AgentSerializer
from tests.factories import AgentFactory


@pytest.mark.django_db
class TestAgentPodNameModel:
    def test_agent_model_has_pod_name_field(self):
        agent = AgentFactory(name="Pod Agent", pod_name="vtf-agent-abc123")
        agent.refresh_from_db()
        assert agent.pod_name == "vtf-agent-abc123"

    def test_agent_pod_name_nullable(self):
        agent = AgentFactory(name="No Pod Agent")
        agent.refresh_from_db()
        assert agent.pod_name is None


@pytest.mark.django_db
class TestAgentPodNameSerializer:
    def test_agent_serializer_includes_pod_name(self):
        agent = AgentFactory(name="Serialized Agent", pod_name="vtf-agent-xyz")
        data = AgentSerializer(agent).data
        assert "pod_name" in data
        assert data["pod_name"] == "vtf-agent-xyz"

    def test_agent_serializer_pod_name_null_when_not_set(self):
        agent = AgentFactory(name="No Pod")
        data = AgentSerializer(agent).data
        assert "pod_name" in data
        assert data["pod_name"] is None


@pytest.mark.django_db
class TestAgentPodNameAPI:
    def test_agent_registration_accepts_pod_name(self, api_client):
        payload = {"name": "Pod Agent", "pod_name": "vtf-agent-reg1"}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        )
        agent = Agent.objects.get(id=response.data["id"])
        assert agent.pod_name == "vtf-agent-reg1"

    def test_agent_update_pod_name(self, api_client):
        agent = AgentFactory(name="Patchable Agent")
        response = api_client.patch(
            f"/v1/agents/{agent.id}/",
            {"pod_name": "vtf-agent-updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        agent.refresh_from_db()
        assert agent.pod_name == "vtf-agent-updated"
