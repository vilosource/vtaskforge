import pytest
from unittest.mock import patch

from events.models import TaskEvent
from events.services import record_event
from tests.factories import TaskFactory


@pytest.mark.django_db
class TestRecordEvent:
    def test_record_event_creates_event(self):
        task = TaskFactory()
        record_event(task, "status_changed", data={"from": "draft", "to": "todo"}, triggered_by="system")
        assert TaskEvent.objects.filter(task=task, event_type="status_changed").count() == 1
        event = TaskEvent.objects.get(task=task, event_type="status_changed")
        assert event.data == {"from": "draft", "to": "todo"}
        assert event.triggered_by == "system"

    def test_record_event_silent_on_error(self):
        task = TaskFactory()
        with patch("events.services.TaskEvent.objects.create", side_effect=Exception("db error")):
            # Must not raise
            result = record_event(task, "status_changed")
        assert result is None

    def test_record_event_returns_event(self):
        task = TaskFactory()
        result = record_event(task, "claimed", data={"agent_id": "agent-1"}, triggered_by="agent-1")
        assert result is not None
        assert isinstance(result, TaskEvent)
        assert result.pk is not None
        assert result.event_type == "claimed"
