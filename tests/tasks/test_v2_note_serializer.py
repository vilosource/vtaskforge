"""Step 6: v2 Note serializer tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from tasks.models import Task, Note
    from prefs.models import ProjectMembership

    user = User.objects.create_user("notev2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="NoteProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    task = Task.objects.create(title="NoteTask", project=project, created_by=user)
    note = Note.objects.create(task=task, text="Test note", actor=user)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, task, note


class TestNoteV2:
    def test_v2_note_actor_is_actor_ref(self, setup):
        """DoD #8"""
        client, task, note = setup
        resp = client.get(f"/v2/tasks/{task.id}/notes/")
        assert resp.status_code == 200
        n = resp.data["results"][0]
        assert isinstance(n["actor"], dict)
        assert n["actor"]["type"] == "user"

    def test_v2_note_task_is_task_ref(self, setup):
        """DoD #9"""
        client, task, note = setup
        resp = client.get(f"/v2/tasks/{task.id}/notes/")
        n = resp.data["results"][0]
        assert isinstance(n["task"], dict)
        assert n["task"]["id"] == task.id

    def test_v2_note_no_legacy_actor_id(self, setup):
        """DoD #10"""
        client, task, note = setup
        resp = client.get(f"/v2/tasks/{task.id}/notes/")
        n = resp.data["results"][0]
        assert "actor_id" not in n

    def test_v1_note_still_has_actor_id(self, setup):
        """DoD #11"""
        client, task, note = setup
        resp = client.get(f"/v1/tasks/{task.id}/notes/")
        n = resp.data["results"][0]
        assert "actor_id" in n
        assert isinstance(n["actor_id"], str)
