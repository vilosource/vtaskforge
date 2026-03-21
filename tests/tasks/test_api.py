"""
Tests for Task CRUD API endpoints.
"""
import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from tasks.models import Task
from tests.factories import LinkFactory, MilestoneFactory, ReviewFactory, TaskEventFactory, TaskFactory, WorkplanFactory
from workplans.models import Milestone


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
def task(db, milestone, workplan):
    return TaskFactory(title="Test Task", milestone=milestone, workplan=workplan)


@pytest.fixture
def doing_task(db, milestone, workplan):
    return TaskFactory(
        title="Doing Task",
        milestone=milestone,
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
        assert response.data["results"] == []

    def test_list_returns_tasks(self, api_client, task):
        response = api_client.get("/v1/tasks/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == task.id

    def test_filter_by_status(self, api_client, task, doing_task):
        response = api_client.get("/v1/tasks/?status=doing")
        assert response.status_code == status.HTTP_200_OK
        assert all(t["status"] == "doing" for t in response.data["results"])
        assert len(response.data["results"]) == 1

    def test_filter_by_phase(self, api_client, task, milestone):
        response = api_client.get(f"/v1/tasks/?milestone={milestone.id}")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_filter_by_workplan(self, api_client, task, workplan):
        response = api_client.get(f"/v1/tasks/?workplan={workplan.id}")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_filter_by_assigned_to(self, api_client, milestone, workplan):
        TaskFactory(title="Assigned", milestone=milestone, workplan=workplan, assigned_to="bob")
        TaskFactory(title="Unassigned", milestone=milestone, workplan=workplan)
        response = api_client.get("/v1/tasks/?assigned_to=bob")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["assigned_to"] == "bob"

    def test_filter_by_unknown_status_returns_empty(self, api_client, task):
        response = api_client.get("/v1/tasks/?status=nonexistent")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskCreate:
    def test_create_returns_201(self, api_client, milestone, workplan):
        payload = {"title": "New Task", "milestone": milestone.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_default_status_to_draft(self, api_client, milestone, workplan):
        payload = {"title": "New Task", "milestone": milestone.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.data["status"] == "draft"

    def test_create_returns_nanoid(self, api_client, milestone, workplan):
        payload = {"title": "New Task", "milestone": milestone.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_status_is_read_only(self, api_client, milestone, workplan):
        payload = {"title": "New Task", "milestone": milestone.id, "workplan": workplan.id, "status": "done"}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "draft"

    def test_create_id_is_read_only(self, api_client, milestone, workplan):
        payload = {"title": "New Task", "milestone": milestone.id, "workplan": workplan.id, "id": "custom-id-12345678901"}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["id"] != "custom-id-12345678901"

    def test_create_without_title_returns_400(self, api_client, milestone, workplan):
        payload = {"milestone": milestone.id, "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_phase_returns_400(self, api_client, workplan):
        payload = {"title": "Task", "workplan": workplan.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_without_workplan_returns_400(self, api_client, milestone):
        payload = {"title": "Task", "milestone": milestone.id}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_all_fields(self, api_client, milestone, workplan):
        payload = {
            "title": "Full Task",
            "description": "A detailed description",
            "milestone": milestone.id,
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

    def test_create_persists_to_db(self, api_client, milestone, workplan):
        payload = {"title": "Persist Task", "milestone": milestone.id, "workplan": workplan.id}
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
    def test_list_returns_200(self, api_client, milestone, task):
        response = api_client.get(f"/v1/phases/{milestone.id}/tasks/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_tasks_in_phase(self, api_client, milestone, task):
        response = api_client.get(f"/v1/phases/{milestone.id}/tasks/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == task.id

    def test_list_returns_404_for_unknown_phase(self, api_client):
        response = api_client.get("/v1/phases/nonexistentid12345678/tasks/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_auto_sets_phase_and_workplan(self, api_client, milestone, workplan):
        payload = {"title": "Nested Task"}
        response = api_client.post(f"/v1/phases/{milestone.id}/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["milestone"] == milestone.id
        assert response.data["workplan"] == workplan.id

    def test_create_returns_404_for_unknown_phase(self, api_client):
        payload = {"title": "Task"}
        response = api_client.post("/v1/phases/nonexistentid12345678/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_without_title_returns_400(self, api_client, milestone):
        response = api_client.post(f"/v1/phases/{milestone.id}/tasks/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_persists_with_correct_relationships(self, api_client, milestone, workplan):
        payload = {"title": "Nested Task"}
        response = api_client.post(f"/v1/phases/{milestone.id}/tasks/", payload, format="json")
        task = Task.objects.get(id=response.data["id"])
        assert task.milestone_id == milestone.id
        assert task.workplan_id == workplan.id

    def test_list_filters_by_status(self, api_client, milestone, workplan):
        TaskFactory(title="Draft Task", milestone=milestone, workplan=workplan, status="draft")
        TaskFactory(title="Doing Task", milestone=milestone, workplan=workplan, status="doing")
        response = api_client.get(f"/v1/phases/{milestone.id}/tasks/?status=draft")
        assert response.status_code == status.HTTP_200_OK
        assert all(t["status"] == "draft" for t in response.data["results"])

    def test_list_does_not_include_tasks_from_other_milestones(self, api_client, workplan, milestone, task):
        other_milestone = MilestoneFactory(name="Other Phase", workplan=workplan)
        TaskFactory(title="Other Task", milestone=other_milestone, workplan=workplan)
        response = api_client.get(f"/v1/phases/{milestone.id}/tasks/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == task.id


# ---------------------------------------------------------------------------
# Session authentication
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSessionAuthentication:
    """Verify that session-based (cookie) auth works alongside token auth."""

    def test_session_auth_can_access_task_list(self, db):
        user = User.objects.create_user(username="sessionuser", password="sessionpass")
        client = APIClient()
        # Log in via Django session
        client.login(username="sessionuser", password="sessionpass")
        # Must enforce CSRF for session auth; use enforce_csrf_checks=False in test client
        response = client.get("/v1/tasks/")
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_returns_401(self, db):
        client = APIClient()
        response = client.get("/v1/tasks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_auth_still_works(self, db):
        user = User.objects.create_user(username="tokenuser2", password="pass")
        token = Token.objects.create(user=user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.get("/v1/tasks/")
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# Expand parameter: GET /v1/tasks/:id?expand=links,reviews,events
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskDetailExpand:
    """Verify ?expand= parameter on retrieve endpoint."""

    def test_no_expand_returns_null_fields(self, api_client, task):
        response = api_client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_200_OK
        # Without expand, extra fields are NOT present (uses TaskSerializer)
        assert "links" not in response.data
        assert "reviews" not in response.data
        assert "events" not in response.data

    def test_expand_links_returns_list(self, api_client, task):
        LinkFactory(source_type="task", source_id=task.id, link_type="relates_to")
        response = api_client.get(f"/v1/tasks/{task.id}/?expand=links")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["links"] is not None
        assert isinstance(response.data["links"], list)
        assert len(response.data["links"]) == 1

    def test_expand_reviews_returns_list(self, api_client, task):
        ReviewFactory(task=task)
        response = api_client.get(f"/v1/tasks/{task.id}/?expand=reviews")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["reviews"] is not None
        assert isinstance(response.data["reviews"], list)
        assert len(response.data["reviews"]) == 1

    def test_expand_events_returns_list(self, api_client, task):
        TaskEventFactory(task=task, event_type="status_changed", data={})
        response = api_client.get(f"/v1/tasks/{task.id}/?expand=events")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["events"] is not None
        assert isinstance(response.data["events"], list)
        assert len(response.data["events"]) == 1

    def test_expand_all_three(self, api_client, task):
        LinkFactory(source_type="task", source_id=task.id, link_type="relates_to")
        ReviewFactory(task=task)
        TaskEventFactory(task=task, event_type="claimed", data={})
        response = api_client.get(f"/v1/tasks/{task.id}/?expand=links,reviews,events")
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data["links"], list)
        assert isinstance(response.data["reviews"], list)
        assert isinstance(response.data["events"], list)

    def test_expand_non_requested_field_is_null(self, api_client, task):
        """When only links is expanded, reviews and events must be None."""
        response = api_client.get(f"/v1/tasks/{task.id}/?expand=links")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["reviews"] is None
        assert response.data["events"] is None

    def test_expand_only_on_detail_not_list(self, api_client, task):
        """The list endpoint should not include expand fields."""
        response = api_client.get("/v1/tasks/?expand=links,reviews,events")
        assert response.status_code == status.HTTP_200_OK
        result = response.data["results"][0]
        assert "links" not in result
        assert "reviews" not in result
        assert "events" not in result

    def test_expand_empty_relations_return_empty_list(self, api_client, task):
        """Expanded fields with no related objects return [] not None."""
        response = api_client.get(f"/v1/tasks/{task.id}/?expand=links,reviews,events")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["links"] == []
        assert response.data["reviews"] == []
        assert response.data["events"] == []


# ---------------------------------------------------------------------------
# Multi-status filter: ?status=doing,blocked
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMultiStatusFilter:
    """Verify comma-separated ?status= filter."""

    def test_single_status_filter_works(self, api_client, milestone, workplan):
        TaskFactory(title="Draft Task", milestone=milestone, workplan=workplan, status="draft")
        TaskFactory(title="Doing Task", milestone=milestone, workplan=workplan, status="doing")
        response = api_client.get("/v1/tasks/?status=doing")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["status"] == "doing"

    def test_multi_status_filter_returns_all_matching(self, api_client, milestone, workplan):
        TaskFactory(title="Draft Task", milestone=milestone, workplan=workplan, status="draft")
        TaskFactory(title="Doing Task", milestone=milestone, workplan=workplan, status="doing")
        TaskFactory(title="Blocked Task", milestone=milestone, workplan=workplan, status="blocked")
        response = api_client.get("/v1/tasks/?status=doing,blocked")
        assert response.status_code == status.HTTP_200_OK
        statuses = {t["status"] for t in response.data["results"]}
        assert statuses == {"doing", "blocked"}
        assert len(response.data["results"]) == 2

    def test_multi_status_excludes_non_matching(self, api_client, milestone, workplan):
        TaskFactory(title="Draft Task", milestone=milestone, workplan=workplan, status="draft")
        TaskFactory(title="Doing Task", milestone=milestone, workplan=workplan, status="doing")
        response = api_client.get("/v1/tasks/?status=doing,blocked")
        assert response.status_code == status.HTTP_200_OK
        assert all(t["status"] != "draft" for t in response.data["results"])

    def test_multi_status_three_values(self, api_client, milestone, workplan):
        TaskFactory(title="Draft Task", milestone=milestone, workplan=workplan, status="draft")
        TaskFactory(title="Doing Task", milestone=milestone, workplan=workplan, status="doing")
        TaskFactory(title="Blocked Task", milestone=milestone, workplan=workplan, status="blocked")
        TaskFactory(title="Done Task", milestone=milestone, workplan=workplan, status="done")
        response = api_client.get("/v1/tasks/?status=draft,doing,blocked")
        assert response.status_code == status.HTTP_200_OK
        statuses = {t["status"] for t in response.data["results"]}
        assert "done" not in statuses
        assert len(response.data["results"]) == 3
