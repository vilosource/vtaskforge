"""
Tests for Note model and nested notes API endpoint.
"""
import pytest
from rest_framework import status

from tasks.models import Note, Task
from tests.factories import NoteFactory, MilestoneFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def milestone(db, workplan):
    return MilestoneFactory(name="Test Phase", workplan=workplan)


@pytest.fixture
def task(db, phase, workplan):
    return TaskFactory(title="Test Task", milestone=phase, workplan=workplan)


@pytest.fixture
def note(db, task):
    return NoteFactory(task=task, text="First note", actor_id="agent-1")


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNoteModel:
    def test_create_note(self, task):
        note = NoteFactory(task=task, text="Hello world", actor_id="agent-1")
        assert note.id is not None
        assert len(note.id) == 21
        assert note.task == task
        assert note.text == "Hello world"
        assert note.actor_id == "agent-1"
        assert note.created_at is not None

    def test_note_str_truncates(self, task):
        long_text = "A" * 100
        note = NoteFactory(task=task, text=long_text, actor_id="agent-1")
        assert str(note) == long_text[:50]

    def test_note_str_short_text(self, task):
        note = NoteFactory(task=task, text="Short", actor_id="agent-1")
        assert str(note) == "Short"

    def test_cascade_delete(self, task, note):
        note_id = note.id
        task.delete()
        assert not Note.objects.filter(id=note_id).exists()

    def test_ordering_ascending(self, task):
        note1 = NoteFactory(task=task, text="First", actor_id="agent-1")
        note2 = NoteFactory(task=task, text="Second", actor_id="agent-2")
        notes = list(Note.objects.filter(task=task))
        assert notes[0].id == note1.id
        assert notes[1].id == note2.id

    def test_no_updated_at_field(self, task):
        note = NoteFactory(task=task, text="Test", actor_id="agent-1")
        assert not hasattr(note, "updated_at")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNoteList:
    def test_list_returns_200(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/notes/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_empty(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/notes/")
        assert response.data["results"] == []

    def test_list_returns_notes(self, api_client, task, note):
        response = api_client.get(f"/v1/tasks/{task.id}/notes/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == note.id
        assert response.data["results"][0]["text"] == note.text
        assert response.data["results"][0]["actor_id"] == note.actor_id

    def test_list_404_if_task_not_found(self, api_client):
        response = api_client.get("/v1/tasks/nonexistent-task-id/notes/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_only_returns_notes_for_task(self, api_client, phase, workplan, task):
        other_task = TaskFactory(title="Other Task", milestone=phase, workplan=workplan)
        NoteFactory(task=task, text="Task note", actor_id="agent-1")
        NoteFactory(task=other_task, text="Other note", actor_id="agent-2")
        response = api_client.get(f"/v1/tasks/{task.id}/notes/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["text"] == "Task note"

    def test_list_ordered_ascending(self, api_client, task):
        NoteFactory(task=task, text="First", actor_id="agent-1")
        NoteFactory(task=task, text="Second", actor_id="agent-2")
        response = api_client.get(f"/v1/tasks/{task.id}/notes/")
        assert response.data["results"][0]["text"] == "First"
        assert response.data["results"][1]["text"] == "Second"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNoteCreate:
    def test_create_returns_201(self, api_client, task):
        response = api_client.post(
            f"/v1/tasks/{task.id}/notes/",
            {"text": "A note", "actor_id": "agent-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_task_from_url(self, api_client, task):
        response = api_client.post(
            f"/v1/tasks/{task.id}/notes/",
            {"text": "A note", "actor_id": "agent-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["task"] == task.id

    def test_create_persists_note(self, api_client, task):
        api_client.post(
            f"/v1/tasks/{task.id}/notes/",
            {"text": "Saved note", "actor_id": "agent-1"},
            format="json",
        )
        assert Note.objects.filter(task=task, text="Saved note").exists()

    def test_create_404_if_task_not_found(self, api_client):
        response = api_client.post(
            "/v1/tasks/nonexistent-id/notes/",
            {"text": "A note", "actor_id": "agent-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_requires_text(self, api_client, task):
        response = api_client.post(
            f"/v1/tasks/{task.id}/notes/",
            {"actor_id": "agent-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_requires_actor_id(self, api_client, task):
        response = api_client.post(
            f"/v1/tasks/{task.id}/notes/",
            {"text": "A note"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_response_has_id_and_created_at(self, api_client, task):
        response = api_client.post(
            f"/v1/tasks/{task.id}/notes/",
            {"text": "A note", "actor_id": "agent-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.data
        assert "created_at" in response.data

    def test_no_update_endpoint(self, api_client, task, note):
        response = api_client.patch(
            f"/v1/tasks/{task.id}/notes/{note.id}/",
            {"text": "Modified"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_no_delete_endpoint(self, api_client, task, note):
        response = api_client.delete(f"/v1/tasks/{task.id}/notes/{note.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
