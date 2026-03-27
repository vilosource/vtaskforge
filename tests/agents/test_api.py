from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status

from agents.models import Agent
from tests.factories import AgentFactory, TaskFactory


@pytest.fixture
def agent(db):
    return AgentFactory(name="Test Agent", tags=["python"], status="online")


@pytest.fixture
def offline_agent(db):
    return AgentFactory(name="Offline Agent", status="offline")


@pytest.mark.django_db
class TestAgentList:
    def test_list_returns_200(self, api_client):
        response = api_client.get("/v1/agents/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_empty_when_no_agents(self, api_client):
        response = api_client.get("/v1/agents/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_list_returns_agents(self, api_client, agent):
        response = api_client.get("/v1/agents/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == agent.id
        assert response.data["results"][0]["name"] == agent.name


@pytest.mark.django_db
class TestAgentCreate:
    def test_create_returns_201(self, api_client):
        payload = {"name": "New Agent", "tags": []}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_status_online(self, api_client):
        payload = {"name": "New Agent", "tags": []}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert response.data["status"] == "online"

    def test_create_ignores_provided_status(self, api_client):
        # Even if client provides status=offline, create always sets online
        payload = {"name": "New Agent", "tags": [], "status": "offline"}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "online"

    def test_create_returns_id(self, api_client):
        payload = {"name": "New Agent"}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_returns_token(self, api_client):
        payload = {"name": "New Agent"}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert "token" in response.data
        assert len(response.data["token"]) == 40

    def test_create_with_tags(self, api_client):
        payload = {"name": "Tagged Agent", "tags": ["python", "llm"]}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["tags"] == ["python", "llm"]

    def test_create_without_name_returns_400(self, api_client):
        response = api_client.post("/v1/agents/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_persists_to_db(self, api_client):
        payload = {"name": "Persistent Agent"}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert Agent.objects.filter(id=response.data["id"]).exists()

    def test_create_id_is_read_only(self, api_client):
        payload = {"name": "Test", "id": "custom-id-12345678901"}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["id"] != "custom-id-12345678901"

    def test_create_returns_registered_at(self, api_client):
        payload = {"name": "New Agent"}
        response = api_client.post("/v1/agents/", payload, format="json")
        assert "registered_at" in response.data
        assert response.data["registered_at"] is not None


@pytest.mark.django_db
class TestAgentRetrieve:
    def test_retrieve_returns_200(self, api_client, agent):
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_returns_correct_data(self, api_client, agent):
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["id"] == agent.id
        assert response.data["name"] == agent.name

    def test_retrieve_returns_all_fields(self, api_client, agent):
        response = api_client.get(f"/v1/agents/{agent.id}/")
        expected_fields = [
            "id", "name", "tags", "status", "last_heartbeat",
            "registered_at", "created_at", "updated_at",
        ]
        for field in expected_fields:
            assert field in response.data

    def test_retrieve_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/agents/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAgentPartialUpdate:
    def test_patch_returns_200(self, api_client, agent):
        response = api_client.patch(
            f"/v1/agents/{agent.id}/",
            {"status": "busy"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patch_updates_status(self, api_client, agent):
        response = api_client.patch(
            f"/v1/agents/{agent.id}/",
            {"status": "busy"},
            format="json",
        )
        assert response.data["status"] == "busy"

    def test_patch_updates_tags(self, api_client, agent):
        response = api_client.patch(
            f"/v1/agents/{agent.id}/",
            {"tags": ["new-tag"]},
            format="json",
        )
        assert response.data["tags"] == ["new-tag"]

    def test_patch_persists_to_db(self, api_client, agent):
        api_client.patch(
            f"/v1/agents/{agent.id}/",
            {"status": "offline"},
            format="json",
        )
        agent.refresh_from_db()
        assert agent.status == "offline"

    def test_patch_does_not_affect_other_fields(self, api_client, agent):
        original_name = agent.name
        api_client.patch(
            f"/v1/agents/{agent.id}/",
            {"status": "busy"},
            format="json",
        )
        agent.refresh_from_db()
        assert agent.name == original_name

    def test_put_not_allowed(self, api_client, agent):
        response = api_client.put(
            f"/v1/agents/{agent.id}/",
            {"name": "Updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_id_is_read_only(self, api_client, agent):
        original_id = agent.id
        api_client.patch(
            f"/v1/agents/{agent.id}/",
            {"id": "newid1234567890123456"},
            format="json",
        )
        agent.refresh_from_db()
        assert agent.id == original_id


@pytest.mark.django_db
class TestAgentDelete:
    def test_delete_returns_204(self, api_client, agent):
        response = api_client.delete(f"/v1/agents/{agent.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_removes_from_db(self, api_client, agent):
        agent_id = agent.id
        api_client.delete(f"/v1/agents/{agent.id}/")
        assert not Agent.objects.filter(id=agent_id).exists()

    def test_delete_nonexistent_returns_404(self, api_client):
        response = api_client.delete("/v1/agents/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAgentComputedFields:
    """Tests for computed fields: current_task, tasks_completed, tasks_failed, effective_status."""

    def test_current_task_populated_when_agent_has_doing_task(self, api_client, agent):
        task = TaskFactory(status="doing", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["current_task"] is not None
        assert response.data["current_task"]["id"] == task.id
        assert response.data["current_task"]["title"] == task.title
        assert response.data["current_task"]["status"] == "doing"

    def test_current_task_null_when_no_doing_task(self, api_client, agent):
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["current_task"] is None

    def test_current_task_null_when_task_is_done(self, api_client, agent):
        TaskFactory(status="done", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["current_task"] is None

    def test_tasks_completed_count(self, api_client, agent):
        for _ in range(3):
            TaskFactory(status="done", claimed_by=agent.id)
        TaskFactory(status="doing", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["tasks_completed"] == 3

    def test_tasks_completed_zero_when_none(self, api_client, agent):
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["tasks_completed"] == 0

    def test_tasks_failed_count(self, api_client, agent):
        for _ in range(2):
            TaskFactory(status="needs_attention", claimed_by=agent.id)
        TaskFactory(status="done", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["tasks_failed"] == 2

    def test_tasks_failed_zero_when_none(self, api_client, agent):
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["tasks_failed"] == 0

    def test_effective_status_stale_for_old_heartbeat(self, api_client, db):
        agent = AgentFactory(
            status="online",
            last_heartbeat=timezone.now() - timedelta(minutes=10),
        )
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["effective_status"] == "stale"

    def test_effective_status_online_for_recent_heartbeat(self, api_client, db):
        agent = AgentFactory(
            status="online",
            last_heartbeat=timezone.now() - timedelta(seconds=30),
        )
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["effective_status"] == "online"

    def test_effective_status_stale_when_no_heartbeat(self, api_client, db):
        agent = AgentFactory(status="online", last_heartbeat=None)
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["effective_status"] == "stale"

    def test_effective_status_preserves_offline(self, api_client, db):
        agent = AgentFactory(status="offline", last_heartbeat=None)
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["effective_status"] == "offline"

    def test_effective_status_preserves_busy(self, api_client, db):
        agent = AgentFactory(
            status="busy",
            last_heartbeat=timezone.now() - timedelta(minutes=10),
        )
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["effective_status"] == "busy"

    def test_computed_fields_in_list(self, api_client, agent):
        TaskFactory(status="doing", claimed_by=agent.id)
        response = api_client.get("/v1/agents/")
        result = response.data["results"][0]
        assert "current_task" in result
        assert "tasks_completed" in result
        assert "tasks_failed" in result
        assert "effective_status" in result

    def test_counts_exclude_other_agents_tasks(self, api_client, agent):
        other = AgentFactory(name="Other Agent")
        TaskFactory(status="done", claimed_by=other.id)
        TaskFactory(status="done", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/")
        assert response.data["tasks_completed"] == 1


@pytest.mark.django_db
class TestAgentTasks:
    def test_tasks_returns_200(self, api_client, agent):
        response = api_client.get(f"/v1/agents/{agent.id}/tasks/")
        assert response.status_code == status.HTTP_200_OK

    def test_tasks_returns_claimed_tasks(self, api_client, agent):
        t1 = TaskFactory(status="doing", claimed_by=agent.id)
        t2 = TaskFactory(status="done", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/tasks/")
        ids = [t["id"] for t in response.data["results"]]
        assert t1.id in ids
        assert t2.id in ids

    def test_tasks_excludes_other_agents_tasks(self, api_client, agent):
        other = AgentFactory(name="Other Agent")
        TaskFactory(status="doing", claimed_by=other.id)
        TaskFactory(status="doing", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/tasks/")
        assert len(response.data["results"]) == 1

    def test_tasks_filters_by_status(self, api_client, agent):
        TaskFactory(status="doing", claimed_by=agent.id)
        TaskFactory(status="done", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/tasks/?status=done")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["status"] == "done"

    def test_tasks_returns_paginated_response(self, api_client, agent):
        TaskFactory(status="doing", claimed_by=agent.id)
        response = api_client.get(f"/v1/agents/{agent.id}/tasks/")
        assert "results" in response.data
        assert "next" in response.data
        assert "previous" in response.data

    def test_tasks_nonexistent_agent_returns_404(self, api_client):
        response = api_client.get("/v1/agents/nonexistentid12345678/tasks/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
