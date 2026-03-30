"""
Tests for claimed_by_pod_name field in task serializers and API.
"""
import pytest
from rest_framework import status

from tasks.serializers import TaskSerializer
from tests.factories import AgentFactory, TaskFactory


@pytest.mark.django_db
class TestTaskClaimedByPodName:
    def test_task_serializer_includes_claimed_by_pod_name(self):
        agent = AgentFactory(name="Pod Agent", pod_name="vtf-agent-pod1")
        task = TaskFactory(status="doing", claimed_by=agent.id)
        data = TaskSerializer(task).data
        assert "claimed_by_pod_name" in data
        assert data["claimed_by_pod_name"] == "vtf-agent-pod1"

    def test_claimed_by_pod_name_null_when_unclaimed(self):
        task = TaskFactory(status="draft")
        data = TaskSerializer(task).data
        assert "claimed_by_pod_name" in data
        assert data["claimed_by_pod_name"] is None

    def test_claimed_by_pod_name_null_when_agent_has_no_pod(self):
        agent = AgentFactory(name="No Pod Agent")
        task = TaskFactory(status="doing", claimed_by=agent.id)
        data = TaskSerializer(task).data
        assert "claimed_by_pod_name" in data
        assert data["claimed_by_pod_name"] is None

    def test_task_list_includes_claimed_by_pod_name(self, api_client):
        agent = AgentFactory(name="List Agent", pod_name="vtf-agent-list")
        TaskFactory(status="doing", claimed_by=agent.id)
        response = api_client.get("/v1/tasks/")
        assert response.status_code == status.HTTP_200_OK
        task_data = response.data["results"][0]
        assert "claimed_by_pod_name" in task_data
        assert task_data["claimed_by_pod_name"] == "vtf-agent-list"
