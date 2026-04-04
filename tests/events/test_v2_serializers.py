"""Step 6: v2 TaskEvent serializer tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from tasks.models import Task
    from events.models import TaskEvent
    from prefs.models import ProjectMembership

    user = User.objects.create_user("evtv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="EvtProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    task = Task.objects.create(title="EvtTask", project=project, created_by=user)

    # Event with actor (user-triggered)
    evt_user = TaskEvent.objects.create(
        task=task, event_type="status_changed",
        trigger_source="submit", actor=user,
    )
    # Event without actor (system-triggered)
    evt_sys = TaskEvent.objects.create(
        task=task, event_type="claim_expired",
        trigger_source="system", actor=None,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, task, evt_user, evt_sys


class TestEventV2:
    def test_v2_event_actor_is_actor_ref(self, setup):
        """DoD #12"""
        client, task, evt_user, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/events/")
        assert resp.status_code == 200
        # Find the event with actor
        events = resp.data["results"]
        user_evt = next(e for e in events if e["event_type"] == "status_changed")
        assert isinstance(user_evt["actor"], dict)
        assert user_evt["actor"]["type"] == "user"

    def test_v2_event_actor_null_for_system(self, setup):
        """DoD #13"""
        client, task, _, evt_sys = setup
        resp = client.get(f"/v2/tasks/{task.id}/events/")
        events = resp.data["results"]
        sys_evt = next(e for e in events if e["event_type"] == "claim_expired")
        assert sys_evt["actor"] is None

    def test_v2_event_trigger_source_is_string(self, setup):
        """DoD #14"""
        client, task, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/events/")
        events = resp.data["results"]
        assert isinstance(events[0]["trigger_source"], str)

    def test_v2_event_task_is_task_ref(self, setup):
        """DoD #15"""
        client, task, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/events/")
        events = resp.data["results"]
        assert isinstance(events[0]["task"], dict)
        assert events[0]["task"]["id"] == task.id

    def test_v1_event_triggered_by_unchanged(self, setup):
        """DoD #16"""
        client, task, _, _ = setup
        resp = client.get(f"/v1/tasks/{task.id}/events/")
        events = resp.data["results"]
        # v1 has triggered_by as a string
        assert "triggered_by" in events[0]
        assert isinstance(events[0]["triggered_by"], str)
