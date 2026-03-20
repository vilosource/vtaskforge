"""
Tests verifying that TaskEvents are auto-created during state transitions,
claim actions, and unclaim actions.
"""
import pytest

from events.models import TaskEvent
from tasks.exceptions import InvalidTransition
from tasks.state_machine import perform_transition
from tests.factories import PhaseFactory, TaskFactory, WorkplanFactory


def make_task(status="draft", **kwargs):
    return TaskFactory(status=status, **kwargs)


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def phase(db, workplan):
    return PhaseFactory(name="Test Phase", workplan=workplan)


@pytest.fixture
def task(db, phase, workplan):
    return TaskFactory(title="Test Task", phase=phase, workplan=workplan)


# ---------------------------------------------------------------------------
# State machine auto-logging
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStateMachineAutoLogging:
    def test_perform_transition_creates_event(self):
        task = make_task("draft")
        perform_transition(task, "todo", triggered_by="system")
        events = TaskEvent.objects.filter(task=task, event_type="status_changed")
        assert events.count() == 1

    def test_event_has_correct_from_and_to(self):
        task = make_task("draft")
        perform_transition(task, "todo", triggered_by="system")
        event = TaskEvent.objects.get(task=task, event_type="status_changed")
        assert event.data["from"] == "draft"
        assert event.data["to"] == "todo"

    def test_event_triggered_by_is_set(self):
        task = make_task("draft")
        perform_transition(task, "todo", triggered_by="test-agent")
        event = TaskEvent.objects.get(task=task, event_type="status_changed")
        assert event.triggered_by == "test-agent"

    def test_old_status_captured_before_change(self):
        """Verifies that 'from' reflects the pre-transition status."""
        task = make_task("todo")
        perform_transition(task, "doing", triggered_by="agent-1")
        event = TaskEvent.objects.get(task=task, event_type="status_changed")
        assert event.data["from"] == "todo"
        assert event.data["to"] == "doing"

    def test_chained_transitions_create_multiple_events(self):
        task = make_task("draft")
        perform_transition(task, "todo")
        perform_transition(task, "doing")
        perform_transition(task, "done")
        events = TaskEvent.objects.filter(task=task, event_type="status_changed")
        assert events.count() == 3

    def test_invalid_transition_does_not_create_event(self):
        task = make_task("draft")
        with pytest.raises(InvalidTransition):
            perform_transition(task, "doing")
        assert TaskEvent.objects.filter(task=task).count() == 0

    def test_empty_triggered_by_defaults_to_empty_string(self):
        task = make_task("draft")
        perform_transition(task, "todo")
        event = TaskEvent.objects.get(task=task, event_type="status_changed")
        assert event.triggered_by == ""


# ---------------------------------------------------------------------------
# Claim action auto-logging
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestClaimAutoLogging:
    def test_claim_creates_claimed_event(self, api_client, task):
        task.status = "todo"
        task.save(update_fields=["status", "updated_at"])
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json")
        assert response.status_code == 200
        claimed_events = TaskEvent.objects.filter(task=task, event_type="claimed")
        assert claimed_events.count() == 1

    def test_claim_event_has_agent_id(self, api_client, task):
        task.status = "todo"
        task.save(update_fields=["status", "updated_at"])
        api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-42"}, format="json")
        event = TaskEvent.objects.get(task=task, event_type="claimed")
        assert event.data["agent_id"] == "agent-42"

    def test_claim_event_triggered_by_agent_id(self, api_client, task):
        task.status = "todo"
        task.save(update_fields=["status", "updated_at"])
        api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-42"}, format="json")
        event = TaskEvent.objects.get(task=task, event_type="claimed")
        assert event.triggered_by == "agent-42"

    def test_claim_also_creates_status_changed_event(self, api_client, task):
        task.status = "todo"
        task.save(update_fields=["status", "updated_at"])
        api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json")
        # Both status_changed (from state machine) and claimed events should exist
        assert TaskEvent.objects.filter(task=task, event_type="status_changed").count() == 1
        assert TaskEvent.objects.filter(task=task, event_type="claimed").count() == 1

    def test_failed_claim_no_event(self, api_client, task):
        """Claiming a task that's not in 'todo' should fail and create no claimed event."""
        # task is in draft status
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json")
        assert response.status_code == 409
        assert TaskEvent.objects.filter(task=task, event_type="claimed").count() == 0


# ---------------------------------------------------------------------------
# Unclaim action auto-logging
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUnclaimAutoLogging:
    def test_unclaim_creates_unclaimed_event(self, api_client, task):
        task.status = "doing"
        task.claimed_by = "agent-1"
        task.save(update_fields=["status", "claimed_by", "updated_at"])
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert response.status_code == 200
        unclaimed_events = TaskEvent.objects.filter(task=task, event_type="unclaimed")
        assert unclaimed_events.count() == 1

    def test_unclaim_event_has_agent_id_in_data(self, api_client, task):
        task.status = "doing"
        task.claimed_by = "agent-99"
        task.save(update_fields=["status", "claimed_by", "updated_at"])
        api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        event = TaskEvent.objects.get(task=task, event_type="unclaimed")
        assert event.data["agent_id"] == "agent-99"

    def test_unclaim_also_creates_status_changed_event(self, api_client, task):
        """Unclaim produces both status_changed (from state machine) and unclaimed events."""
        task.status = "doing"
        task.claimed_by = "agent-1"
        task.save(update_fields=["status", "claimed_by", "updated_at"])
        api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert TaskEvent.objects.filter(task=task, event_type="status_changed").count() == 1
        assert TaskEvent.objects.filter(task=task, event_type="unclaimed").count() == 1

    def test_unclaim_status_changed_event_has_correct_from_to(self, api_client, task):
        """The status_changed event from unclaim should reflect doing -> todo."""
        task.status = "doing"
        task.claimed_by = "agent-1"
        task.save(update_fields=["status", "claimed_by", "updated_at"])
        api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        event = TaskEvent.objects.get(task=task, event_type="status_changed")
        assert event.data["from"] == "doing"
        assert event.data["to"] == "todo"

    def test_unclaim_invalid_status_no_event(self, api_client, task):
        """Unclaiming a task not in 'doing' should fail and create no event."""
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert response.status_code == 422
        assert TaskEvent.objects.filter(task=task, event_type="unclaimed").count() == 0
