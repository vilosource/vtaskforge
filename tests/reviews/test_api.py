"""
Tests for Review API endpoints (nested under tasks).
"""
import pytest
from rest_framework import status

from reviews.models import Review
from tasks.models import Task
from tests.factories import PhaseFactory, ReviewFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def phase(db, workplan):
    return PhaseFactory(name="Test Phase", workplan=workplan)


@pytest.fixture
def task_pending_start(db, phase, workplan):
    return TaskFactory(
        title="Start Review Task",
        phase=phase,
        workplan=workplan,
        status="pending_start_review",
    )


@pytest.fixture
def task_pending_completion(db, phase, workplan):
    return TaskFactory(
        title="Completion Review Task",
        phase=phase,
        workplan=workplan,
        status="pending_completion_review",
    )


@pytest.fixture
def task_todo(db, phase, workplan):
    return TaskFactory(
        title="Todo Task",
        phase=phase,
        workplan=workplan,
        status="todo",
    )


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewList:
    def test_list_returns_200(self, api_client, task_pending_start):
        response = api_client.get(f"/v1/tasks/{task_pending_start.id}/reviews/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_empty(self, api_client, task_pending_start):
        response = api_client.get(f"/v1/tasks/{task_pending_start.id}/reviews/")
        assert response.data["results"] == []

    def test_list_404_if_task_not_found(self, api_client):
        response = api_client.get("/v1/tasks/nonexistent-task-id/reviews/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_returns_reviews_for_task(self, api_client, task_pending_start):
        ReviewFactory(
            task=task_pending_start,
            decision="approved",
            reviewer_id="user-1",
        )
        # Force to done state so we can query
        task_pending_start.status = "done"
        task_pending_start.save()
        response = api_client.get(f"/v1/tasks/{task_pending_start.id}/reviews/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["decision"] == "approved"

    def test_list_only_returns_reviews_for_task(self, api_client, phase, workplan, task_pending_start):
        other_task = TaskFactory(
            title="Other Task", phase=phase, workplan=workplan, status="pending_start_review"
        )
        ReviewFactory(task=task_pending_start, decision="approved", reviewer_id="user-1")
        ReviewFactory(task=other_task, decision="rejected", reviewer_id="user-2")
        response = api_client.get(f"/v1/tasks/{task_pending_start.id}/reviews/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["decision"] == "approved"


# ---------------------------------------------------------------------------
# Create — approval transitions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewCreateApproved:
    def test_approve_pending_start_review_returns_201(self, api_client, task_pending_start):
        response = api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_approve_pending_start_review_transitions_to_todo(self, api_client, task_pending_start):
        api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        task_pending_start.refresh_from_db()
        assert task_pending_start.status == "todo"

    def test_approve_pending_completion_review_transitions_to_done(
        self, api_client, task_pending_completion
    ):
        api_client.post(
            f"/v1/tasks/{task_pending_completion.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        task_pending_completion.refresh_from_db()
        assert task_pending_completion.status == "done"

    def test_approve_creates_review_record(self, api_client, task_pending_start):
        api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        assert Review.objects.filter(task=task_pending_start, decision="approved").exists()

    def test_approve_response_has_expected_fields(self, api_client, task_pending_start):
        response = api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        assert "id" in response.data
        assert "task" in response.data
        assert "decision" in response.data
        assert "created_at" in response.data
        assert "updated_at" in response.data

    def test_approve_response_task_id_matches(self, api_client, task_pending_start):
        response = api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        assert response.data["task"] == task_pending_start.id


# ---------------------------------------------------------------------------
# Create — rejection/changes_requested transitions
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewCreateRejected:
    def test_reject_pending_start_review_transitions_to_changes_requested(
        self, api_client, task_pending_start
    ):
        api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "rejected", "reviewer_id": "user-1"},
            format="json",
        )
        task_pending_start.refresh_from_db()
        assert task_pending_start.status == "changes_requested"

    def test_reject_sets_review_return_to_pending_start_review(
        self, api_client, task_pending_start
    ):
        api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "rejected", "reviewer_id": "user-1"},
            format="json",
        )
        task_pending_start.refresh_from_db()
        assert task_pending_start.review_return_to == "pending_start_review"

    def test_reject_pending_completion_review_sets_review_return_to(
        self, api_client, task_pending_completion
    ):
        api_client.post(
            f"/v1/tasks/{task_pending_completion.id}/reviews/",
            {"decision": "rejected", "reviewer_id": "user-1"},
            format="json",
        )
        task_pending_completion.refresh_from_db()
        assert task_pending_completion.review_return_to == "pending_completion_review"
        assert task_pending_completion.status == "changes_requested"

    def test_changes_requested_transitions_to_changes_requested(
        self, api_client, task_pending_start
    ):
        api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "changes_requested", "reviewer_id": "user-1"},
            format="json",
        )
        task_pending_start.refresh_from_db()
        assert task_pending_start.status == "changes_requested"

    def test_reject_creates_review_record(self, api_client, task_pending_start):
        api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "rejected", "reviewer_id": "user-1", "reason": "Not ready"},
            format="json",
        )
        assert Review.objects.filter(task=task_pending_start, decision="rejected").exists()

    def test_reject_returns_201(self, api_client, task_pending_start):
        response = api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "rejected", "reviewer_id": "user-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED


# ---------------------------------------------------------------------------
# Create — validation errors
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewCreateValidation:
    def test_returns_400_if_task_not_in_review_state(self, api_client, task_todo):
        response = api_client.post(
            f"/v1/tasks/{task_todo.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_404_if_task_not_found(self, api_client):
        response = api_client.post(
            "/v1/tasks/nonexistent-id/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_decision(self, api_client, task_pending_start):
        response = api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"reviewer_id": "user-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_requires_reviewer_id(self, api_client, task_pending_start):
        response = api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "approved"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_decision_value(self, api_client, task_pending_start):
        response = api_client.post(
            f"/v1/tasks/{task_pending_start.id}/reviews/",
            {"decision": "maybe", "reviewer_id": "user-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_400_error_message_includes_current_status(self, api_client, task_todo):
        response = api_client.post(
            f"/v1/tasks/{task_todo.id}/reviews/",
            {"decision": "approved", "reviewer_id": "user-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "todo" in response.data["detail"]


# ---------------------------------------------------------------------------
# Append-only: no update, no delete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewAppendOnly:
    def test_no_update_endpoint(self, api_client, task_pending_start):
        review = ReviewFactory(
            task=task_pending_start,
            decision="approved",
            reviewer_id="user-1",
        )
        response = api_client.patch(
            f"/v1/tasks/{task_pending_start.id}/reviews/{review.id}/",
            {"reason": "Changed mind"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_no_delete_endpoint(self, api_client, task_pending_start):
        review = ReviewFactory(
            task=task_pending_start,
            decision="approved",
            reviewer_id="user-1",
        )
        response = api_client.delete(
            f"/v1/tasks/{task_pending_start.id}/reviews/{review.id}/"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
