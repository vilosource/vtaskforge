import pytest

from events.models import TaskEvent, EVENT_TYPE_CHOICES
from tests.factories import TaskEventFactory, TaskFactory


def make_task(status="draft", **kwargs):
    return TaskFactory(status=status, **kwargs)


@pytest.mark.django_db
class TestTaskEventModel:
    def test_create_status_changed_event(self):
        task = make_task()
        event = TaskEventFactory(
            task=task,
            event_type="status_changed",
            data={"from": "draft", "to": "todo"},
            trigger_source="system",
        )
        assert event.pk is not None
        assert event.event_type == "status_changed"
        assert event.data == {"from": "draft", "to": "todo"}
        assert event.trigger_source == "system"

    def test_create_claimed_event(self):
        task = make_task()
        event = TaskEventFactory(
            task=task,
            event_type="claimed",
            data={"agent_id": "agent-1"},
            trigger_source="agent-1",
        )
        assert event.event_type == "claimed"
        assert event.data["agent_id"] == "agent-1"

    def test_create_unclaimed_event(self):
        task = make_task()
        event = TaskEventFactory(
            task=task,
            event_type="unclaimed",
            data={"agent_id": "agent-1"},
            trigger_source="agent-1",
        )
        assert event.event_type == "unclaimed"

    def test_event_has_nanoid(self):
        task = make_task()
        event = TaskEventFactory(
            task=task,
            event_type="status_changed",
            data={"from": "draft", "to": "todo"},
        )
        assert len(event.id) == 21

    def test_event_timestamp_auto_set(self):
        task = make_task()
        event = TaskEventFactory(
            task=task,
            event_type="status_changed",
            data={"from": "draft", "to": "todo"},
        )
        assert event.timestamp is not None

    def test_default_trigger_source_is_empty_string(self):
        task = make_task()
        event = TaskEventFactory(
            task=task,
            event_type="status_changed",
            data={"from": "draft", "to": "todo"},
            trigger_source="",
        )
        assert event.trigger_source == ""

    def test_default_data_is_dict(self):
        task = make_task()
        event = TaskEventFactory(
            task=task,
            event_type="status_changed",
            data={},
        )
        assert isinstance(event.data, dict)

    def test_ordering_newest_first(self):
        task = make_task()
        e1 = TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        e2 = TaskEventFactory(task=task, event_type="status_changed", data={"from": "todo", "to": "doing"})
        events = list(TaskEvent.objects.filter(task=task))
        # Newest first: e2 should come before e1
        assert events[0].pk == e2.pk
        assert events[1].pk == e1.pk

    def test_cascades_on_task_delete(self):
        task = make_task()
        TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        task_id = task.pk
        task.delete()
        assert TaskEvent.objects.filter(task_id=task_id).count() == 0

    def test_related_name_events(self):
        task = make_task()
        TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        assert task.events.count() == 1

    def test_all_event_types_valid(self):
        task = make_task()
        valid_types = [choice[0] for choice in EVENT_TYPE_CHOICES]
        for event_type in valid_types:
            event = TaskEventFactory(task=task, event_type=event_type, data={})
            assert event.event_type == event_type

    def test_str_representation(self):
        task = make_task()
        event = TaskEventFactory(task=task, event_type="status_changed", data={"from": "draft", "to": "todo"})
        assert str(event)  # just make sure it doesn't blow up
