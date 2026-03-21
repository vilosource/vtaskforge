import pytest
from rest_framework import status

from events.models import TaskEvent
from tests.factories import MilestoneFactory, TaskEventFactory, TaskFactory, WorkplanFactory


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def milestone(db, workplan):
    return MilestoneFactory(name="Test Phase", workplan=workplan)


@pytest.fixture
def task(db, phase, workplan):
    return TaskFactory(title="Test Task", milestone=milestone, workplan=workplan)


@pytest.fixture
def task2(db, phase, workplan):
    return TaskFactory(title="Test Task 2", milestone=milestone, workplan=workplan)


@pytest.fixture
def event(db, task):
    return TaskEventFactory(
        task=task,
        event_type="status_changed",
        data={"from": "draft", "to": "todo"},
        triggered_by="system",
    )


# ---------------------------------------------------------------------------
# Nested endpoint: GET /v1/tasks/{task_id}/events/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNestedTaskEvents:
    def test_returns_200(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/events/")
        assert response.status_code == status.HTTP_200_OK

    def test_returns_empty_list_when_no_events(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/events/")
        assert response.data["results"] == []

    def test_returns_events_for_task(self, api_client, task, event):
        response = api_client.get(f"/v1/tasks/{task.id}/events/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == event.id

    def test_returns_404_for_nonexistent_task(self, api_client):
        response = api_client.get("/v1/tasks/nonexistent123456789/events/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_only_returns_events_for_that_task(self, api_client, task, task2, event):
        # Create an event for task2
        TaskEventFactory(
            task=task2, event_type="status_changed", data={"from": "draft", "to": "todo"}
        )
        response = api_client.get(f"/v1/tasks/{task.id}/events/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["task"] == task.id

    def test_event_fields_present(self, api_client, task, event):
        response = api_client.get(f"/v1/tasks/{task.id}/events/")
        ev = response.data["results"][0]
        assert "id" in ev
        assert "task" in ev
        assert "event_type" in ev
        assert "data" in ev
        assert "timestamp" in ev
        assert "triggered_by" in ev

    def test_no_write_methods_allowed(self, api_client, task):
        response = api_client.post(f"/v1/tasks/{task.id}/events/", {}, format="json")
        assert response.status_code in (
            status.HTTP_405_METHOD_NOT_ALLOWED,
            status.HTTP_404_NOT_FOUND,
        )


# ---------------------------------------------------------------------------
# Top-level endpoint: GET /v1/events/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTopLevelEvents:
    def test_returns_200(self, api_client):
        response = api_client.get("/v1/events/")
        assert response.status_code == status.HTTP_200_OK

    def test_returns_all_events(self, api_client, task, task2):
        TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        TaskEventFactory(task=task2, event_type="claimed", data={"agent_id": "agent-1"})
        response = api_client.get("/v1/events/")
        assert len(response.data["results"]) == 2

    def test_filter_by_task(self, api_client, task, task2):
        e1 = TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        TaskEventFactory(task=task2, event_type="status_changed", data={"from": "draft", "to": "todo"})
        response = api_client.get(f"/v1/events/?task={task.id}")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == e1.id

    def test_filter_by_event_type(self, api_client, task):
        TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        TaskEventFactory(task=task, event_type="claimed", data={"agent_id": "agent-1"})
        response = api_client.get("/v1/events/?event_type=claimed")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["event_type"] == "claimed"

    def test_filter_by_since(self, api_client, task):
        from django.utils import timezone
        import datetime
        past = timezone.now() - datetime.timedelta(hours=1)
        TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        # Use UTC format (Z suffix) to avoid URL encoding issues with +00:00
        since_str = past.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        response = api_client.get(f"/v1/events/?since={since_str}")
        assert len(response.data["results"]) == 1

    def test_no_write_methods_allowed(self, api_client):
        response = api_client.post("/v1/events/", {}, format="json")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_ordering_newest_first(self, api_client, task):
        e1 = TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        e2 = TaskEventFactory(task=task, event_type="claimed", data={"agent_id": "a"})
        response = api_client.get("/v1/events/")
        assert response.data["results"][0]["id"] == e2.id
        assert response.data["results"][1]["id"] == e1.id
