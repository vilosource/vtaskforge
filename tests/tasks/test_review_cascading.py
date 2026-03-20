"""
Integration tests for review flag cascading via API.

Tests submit and complete lifecycle actions with different flag configurations
to verify the cascade: task -> phase -> workplan.
"""
import pytest
from rest_framework import status

from tasks.models import Task
from tests.factories import PhaseFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workplan_no_review(db):
    return WorkplanFactory(
        name="No Review Workplan",
        default_needs_review_before_start=False,
        default_needs_review_on_completion=False,
    )


@pytest.fixture
def workplan_review_both(db):
    return WorkplanFactory(
        name="Review Both Workplan",
        default_needs_review_before_start=True,
        default_needs_review_on_completion=True,
    )


@pytest.fixture
def phase_no_override(db, workplan_no_review):
    return PhaseFactory(
        name="Phase No Override",
        workplan=workplan_no_review,
        default_needs_review_before_start=None,
        default_needs_review_on_completion=None,
    )


@pytest.fixture
def phase_review_both(db, workplan_no_review):
    return PhaseFactory(
        name="Phase Review Both",
        workplan=workplan_no_review,
        default_needs_review_before_start=True,
        default_needs_review_on_completion=True,
    )


@pytest.fixture
def phase_no_review(db, workplan_review_both):
    """Phase that disables review even though workplan enables it."""
    return PhaseFactory(
        name="Phase No Review",
        workplan=workplan_review_both,
        default_needs_review_before_start=False,
        default_needs_review_on_completion=False,
    )


def make_task(phase, workplan, task_status="draft", **kwargs):
    return TaskFactory(
        title="Test Task",
        phase=phase,
        workplan=workplan,
        status=task_status,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Submit: before_start cascading
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSubmitReviewCascading:
    def test_submit_all_false_goes_to_todo(self, api_client, phase_no_override, workplan_no_review):
        task = make_task(phase_no_override, workplan_no_review, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "todo"

    def test_submit_workplan_before_start_true_goes_to_pending_start_review(
        self, api_client, workplan_review_both, db
    ):
        phase = PhaseFactory(
            name="Phase",
            workplan=workplan_review_both,
            default_needs_review_before_start=None,
            default_needs_review_on_completion=None,
        )
        task = make_task(phase, workplan_review_both, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_start_review"

    def test_submit_phase_before_start_true_goes_to_pending_start_review(
        self, api_client, phase_review_both, workplan_no_review
    ):
        task = make_task(phase_review_both, workplan_no_review, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_start_review"

    def test_submit_task_before_start_true_goes_to_pending_start_review(
        self, api_client, phase_no_override, workplan_no_review
    ):
        task = make_task(
            phase_no_override,
            workplan_no_review,
            "draft",
            needs_review_before_start=True,
        )
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_start_review"

    def test_submit_task_false_overrides_phase_true(
        self, api_client, phase_review_both, workplan_no_review
    ):
        """Explicit False on task overrides phase=True."""
        task = make_task(
            phase_review_both,
            workplan_no_review,
            "draft",
            needs_review_before_start=False,
        )
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "todo"

    def test_submit_task_false_overrides_workplan_true(
        self, api_client, phase_no_review, workplan_review_both
    ):
        """Task=False overrides workplan=True even when phase also disables."""
        task = make_task(
            phase_no_review,
            workplan_review_both,
            "draft",
            needs_review_before_start=False,
        )
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "todo"

    def test_submit_phase_false_overrides_workplan_true(
        self, api_client, phase_no_review, workplan_review_both
    ):
        task = make_task(phase_no_review, workplan_review_both, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "todo"

    def test_submit_persists_to_db(self, api_client, phase_review_both, workplan_no_review):
        task = make_task(phase_review_both, workplan_no_review, "draft")
        api_client.post(f"/v1/tasks/{task.id}/submit/")
        task.refresh_from_db()
        assert task.status == "pending_start_review"


# ---------------------------------------------------------------------------
# Complete: on_completion cascading
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCompleteReviewCascading:
    def test_complete_all_false_goes_to_done(
        self, api_client, phase_no_override, workplan_no_review
    ):
        task = make_task(phase_no_override, workplan_no_review, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "done"

    def test_complete_workplan_on_completion_true_goes_to_pending_completion_review(
        self, api_client, workplan_review_both, db
    ):
        phase = PhaseFactory(
            name="Phase",
            workplan=workplan_review_both,
            default_needs_review_before_start=None,
            default_needs_review_on_completion=None,
        )
        task = make_task(phase, workplan_review_both, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_completion_review"

    def test_complete_phase_on_completion_true_goes_to_pending_completion_review(
        self, api_client, phase_review_both, workplan_no_review
    ):
        task = make_task(phase_review_both, workplan_no_review, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_completion_review"

    def test_complete_task_on_completion_true_goes_to_pending_completion_review(
        self, api_client, phase_no_override, workplan_no_review
    ):
        task = make_task(
            phase_no_override,
            workplan_no_review,
            "doing",
            needs_review_on_completion=True,
        )
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending_completion_review"

    def test_complete_task_false_overrides_phase_true(
        self, api_client, phase_review_both, workplan_no_review
    ):
        """Explicit False on task overrides phase=True."""
        task = make_task(
            phase_review_both,
            workplan_no_review,
            "doing",
            needs_review_on_completion=False,
        )
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "done"

    def test_complete_task_false_overrides_workplan_true(
        self, api_client, phase_no_review, workplan_review_both
    ):
        task = make_task(
            phase_no_review,
            workplan_review_both,
            "doing",
            needs_review_on_completion=False,
        )
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "done"

    def test_complete_phase_false_overrides_workplan_true(
        self, api_client, phase_no_review, workplan_review_both
    ):
        task = make_task(phase_no_review, workplan_review_both, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "done"

    def test_complete_persists_to_db(
        self, api_client, phase_review_both, workplan_no_review
    ):
        task = make_task(phase_review_both, workplan_no_review, "doing")
        api_client.post(f"/v1/tasks/{task.id}/complete/")
        task.refresh_from_db()
        assert task.status == "pending_completion_review"


# ---------------------------------------------------------------------------
# Mixed flag configurations
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMixedFlags:
    def test_before_start_true_on_completion_false(
        self, api_client, phase_no_override, workplan_no_review
    ):
        """Task needs start review but not completion review."""
        task = make_task(
            phase_no_override,
            workplan_no_review,
            "draft",
            needs_review_before_start=True,
            needs_review_on_completion=False,
        )
        # Submit should go to pending_start_review
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.data["status"] == "pending_start_review"

        # Approve start review (transition to todo)
        task.status = "todo"
        task.save()

        # Claim
        task.status = "doing"
        task.save()

        # Complete should go to done (no completion review)
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.data["status"] == "done"

    def test_before_start_false_on_completion_true(
        self, api_client, phase_no_override, workplan_no_review
    ):
        """Task skips start review but requires completion review."""
        task = make_task(
            phase_no_override,
            workplan_no_review,
            "draft",
            needs_review_before_start=False,
            needs_review_on_completion=True,
        )
        # Submit should go directly to todo
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.data["status"] == "todo"

        # Claim
        task.status = "doing"
        task.save()

        # Complete should go to pending_completion_review
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.data["status"] == "pending_completion_review"
