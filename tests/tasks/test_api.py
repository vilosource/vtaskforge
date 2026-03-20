"""
Tests for Task CRUD API endpoints.
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tasks.models import Task
from workplans.models import Phase, Workplan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def workplan(db):
    return Workplan.objects.create(name="Test Workplan")


@pytest.fixture
def phase(db, workplan):
    return Phase.objects.create(name="Test Phase", workplan=workplan)


@pytest.fixture
def task(db, phase, workplan):
    return Task.objects.create(title="Test Task", phase=phase, workplan=workplan)


@pytest.fixture
def doing_task(db, phase, workplan):
    return Task.objects.create(
        title="Doing Task",
        phase=phase,
        workplan=workplan,
        status="doing",
        claimed_by="agent-1",
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskList:
    def test_list_returns_200(self, api_client):
        response = api_client.get("/v1/tasks/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_empty(self, api_client):
        response = api_client.get("/v1/tasks/")
        assert response.data == []

    def test_list_returns_tasks(self, api_client, task):
        response = api_client.get("/v1/tasks/")
        assert len(response.data) == 1
        assert response.data[0]["id"] == task.id

    def test_filter_by_status(self, api_client, task, doing_task):
        response = api_client.get("/v1/tasks/?status=doing")
        assert response.status_code == status.HTTP_200_OK
        assert all(t["status"] == "doing" for t in response.data)
        assert len(response.data) == 1

    def test_filter_by_phase(self, api_client, task, phase):
        response = api_client.get(f"/v1/tasks/?phase={phase.id}")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_filter_by_workplan(self, api_client, task, workplan):
        response = api_client.get(f"/v1/tasks/?workplan={workplan.id}")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_filter_by_assigned_to(self, api_client, phase, workplan):
        Task.objects.create(title="Assigned", phase=phase, workplan=workplan, assigned_to="bob")
        Task.objects.create(title="Unassigned", phase=phase, workplan=workplan)
        response = api_client.get("/v1/tasks/?assigned_to=bob")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["assigned_to"] == "bob"

    def test_filter_by_unknown_status_returns_empty(self, api_client, task):
        response = api_client.get("/v1/tasks/?status=nonexistent")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskCreate:
    def test_create_returns_201(self, api_client, phase, workplan):
        payload = {"title": "New Task", "phase": phase.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_default_status_to_draft(self, api_client, phase, workplan):
        payload = {"title": "New Task", "phase": phase.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.data["status"] == "draft"

    def test_create_returns_nanoid(self, api_client, phase, workplan):
        payload = {"title": "New Task", "phase": phase.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_status_is_read_only(self, api_client, phase, workplan):
        payload = {"title": "New Task", "phase": phase.id, "workplan": workplan.id, "status": "done"}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "draft"

    def test_create_id_is_read_only(self, api_client, phase, workplan):
        payload = {"title": "New Task", "phase": phase.id, "workplan": workplan.id, "id": "custom-id-12345678901"}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["id"] != "custom-id-12345678901"

    def test_create_without_title_returns_400(self, api_client, phase, workplan):
        payload = {"phase": phase.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_phase_returns_400(self, api_client, workplan):
        payload = {"title": "Task", "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_workplan_returns_400(self, api_client, phase):
        payload = {"title": "Task", "phase": phase.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_all_fields(self, api_client, phase, workplan):
        payload = {
            "title": "Full Task",
            "description": "A detailed description",
            "phase": phase.id,
            "workplan": workplan.id,
            "acceptance_criteria": ["AC1", "AC2"],
            "needs_review_before_start": True,
            "needs_review_on_completion": False,
            "created_by": "alice",
        }
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Full Task"
        assert response.data["description"] == "A detailed description"
        assert response.data["acceptance_criteria"] == ["AC1", "AC2"]
        assert response.data["needs_review_before_start"] is True
        assert response.data["needs_review_on_completion"] is False
        assert response.data["created_by"] == "alice"

    def test_create_persists_to_db(self, api_client, phase, workplan):
        payload = {"title": "Persist Task", "phase": phase.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert Task.objects.filter(id=response.data["id"]).exists()


# ---------------------------------------------------------------------------
# Retrieve
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskRetrieve:
    def test_retrieve_returns_200(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_correct_data(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/")
        assert response.data["id"] == task.id
        assert response.data["title"] == task.title

    def test_retrieve_returns_all_fields(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/")
        expected_fields = [
            "id", "title", "description", "status", "phase", "workplan",
            "acceptance_criteria", "needs_review_before_start",
            "needs_review_on_completion", "review_return_to", "requires",
            "assigned_to", "claimed_by", "claimed_at", "claim_timeout",
            "claim_expires_at", "created_by", "created_at", "updated_at",
        ]
        for field in expected_fields:
            assert field in response.data, f"Missing field: {field}"

    def test_retrieve_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/tasks/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Partial Update (PATCH)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskPartialUpdate:
    def test_patch_returns_200(self, api_client, task):
        response = api_client.patch(
            f"/v1/tasks/{task.id}/",
            {"title": "Updated Title"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patch_updates_field(self, api_client, task):
        response = api_client.patch(
            f"/v1/tasks/{task.id}/",
            {"title": "Updated Title"},
            format="json",
        )
        assert response.data["title"] == "Updated Title"

    def test_patch_persists_to_db(self, api_client, task):
        api_client.patch(
            f"/v1/tasks/{task.id}/",
            {"description": "New description"},
            format="json",
        )
        task.refresh_from_db()
        assert task.description == "New description"

    def test_patch_does_not_affect_other_fields(self, api_client, task):
        original_title = task.title
        api_client.patch(
            f"/v1/tasks/{task.id}/",
            {"description": "New description"},
            format="json",
        )
        task.refresh_from_db()
        assert task.title == original_title

    def test_put_not_allowed(self, api_client, task):
        response = api_client.put(
            f"/v1/tasks/{task.id}/",
            {"title": "Updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_status_is_read_only(self, api_client, task):
        api_client.patch(
            f"/v1/tasks/{task.id}/",
            {"status": "done"},
            format="json",
        )
        task.refresh_from_db()
        assert task.status == "draft"

    def test_patch_id_is_read_only(self, api_client, task):
        original_id = task.id
        api_client.patch(
            f"/v1/tasks/{task.id}/",
            {"id": "newid1234567890123456"},
            format="json",
        )
        task.refresh_from_db()
        assert task.id == original_id


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskDelete:
    def test_delete_returns_204(self, api_client, task):
        response = api_client.delete(f"/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_removes_from_db(self, api_client, task):
        task_id = task.id
        api_client.delete(f"/v1/tasks/{task.id}/")
        assert not Task.objects.filter(id=task_id).exists()

    def test_delete_nonexistent_returns_404(self, api_client):
        response = api_client.delete("/v1/tasks/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Nested endpoint: /v1/phases/{phase_id}/tasks/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhaseTasksNested:
    def test_list_returns_200(self, api_client, phase, task):
        response = api_client.get(f"/v1/phases/{phase.id}/tasks/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_tasks_in_phase(self, api_client, phase, task):
        response = api_client.get(f"/v1/phases/{phase.id}/tasks/")
        assert len(response.data) == 1
        assert response.data[0]["id"] == task.id

    def test_list_returns_404_for_unknown_phase(self, api_client):
        response = api_client.get("/v1/phases/nonexistentid12345678/tasks/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_auto_sets_phase_and_workplan(self, api_client, phase, workplan):
        payload = {"title": "Nested Task"}
        response = api_client.post(f"/v1/phases/{phase.id}/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["phase"] == phase.id
        assert response.data["workplan"] == workplan.id

    def test_create_returns_404_for_unknown_phase(self, api_client):
        payload = {"title": "Task"}
        response = api_client.post("/v1/phases/nonexistentid12345678/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_without_title_returns_400(self, api_client, phase):
        response = api_client.post(f"/v1/phases/{phase.id}/tasks/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_persists_with_correct_relationships(self, api_client, phase, workplan):
        payload = {"title": "Nested Task"}
        response = api_client.post(f"/v1/phases/{phase.id}/tasks/", payload, format="json")
        task = Task.objects.get(id=response.data["id"])
        assert task.phase_id == phase.id
        assert task.workplan_id == workplan.id

    def test_list_filters_by_status(self, api_client, phase, workplan):
        Task.objects.create(title="Draft Task", phase=phase, workplan=workplan, status="draft")
        Task.objects.create(title="Doing Task", phase=phase, workplan=workplan, status="doing")
        response = api_client.get(f"/v1/phases/{phase.id}/tasks/?status=draft")
        assert response.status_code == status.HTTP_200_OK
        assert all(t["status"] == "draft" for t in response.data)

    def test_list_does_not_include_tasks_from_other_phases(self, api_client, workplan, phase, task):
        other_phase = Phase.objects.create(name="Other Phase", workplan=workplan)
        Task.objects.create(title="Other Task", phase=other_phase, workplan=workplan)
        response = api_client.get(f"/v1/phases/{phase.id}/tasks/")
        assert len(response.data) == 1
        assert response.data[0]["id"] == task.id
