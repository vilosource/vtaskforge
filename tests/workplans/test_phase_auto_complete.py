"""
Tests for automatic phase completion when all tasks reach terminal status.
"""
import pytest

from tests.factories import PhaseFactory, TaskFactory, WorkplanFactory, AgentFactory

from workplans.completion import maybe_complete_phase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def phase(db, workplan):
    return PhaseFactory(name="Test Phase", workplan=workplan, status="active")


def make_task(phase, status="draft"):
    return TaskFactory(
        title="Test Task",
        phase=phase,
        workplan=phase.workplan,
        status=status,
    )


# ---------------------------------------------------------------------------
# Unit tests: maybe_complete_phase
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMaybeCompletePhaseAllDone:
    def test_completes_phase_when_all_done(self, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "done")
        result = maybe_complete_phase(t1)
        phase.refresh_from_db()
        assert phase.status == "completed"

    def test_returns_phase_when_completed(self, phase):
        t1 = make_task(phase, "done")
        result = maybe_complete_phase(t1)
        assert result == phase


@pytest.mark.django_db
class TestMaybeCompletePhaseTerminalMix:
    def test_completes_with_done_and_cancelled(self, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "cancelled")
        result = maybe_complete_phase(t1)
        phase.refresh_from_db()
        assert phase.status == "completed"

    def test_completes_with_all_cancelled(self, phase):
        t1 = make_task(phase, "cancelled")
        t2 = make_task(phase, "cancelled")
        result = maybe_complete_phase(t1)
        phase.refresh_from_db()
        assert phase.status == "completed"


@pytest.mark.django_db
class TestMaybeCompletePhaseNonTerminalRemain:
    def test_does_not_complete_with_todo_remaining(self, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "todo")
        result = maybe_complete_phase(t1)
        phase.refresh_from_db()
        assert phase.status == "active"

    def test_returns_none_when_not_completed(self, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "doing")
        result = maybe_complete_phase(t1)
        assert result is None

    def test_does_not_complete_with_draft_remaining(self, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "draft")
        result = maybe_complete_phase(t1)
        phase.refresh_from_db()
        assert phase.status == "active"


@pytest.mark.django_db
class TestMaybeCompletePhaseGuards:
    def test_pending_phase_not_completed(self, workplan):
        pending_phase = PhaseFactory(
            name="Pending Phase", workplan=workplan, status="pending"
        )
        make_task(pending_phase, "done")
        result = maybe_complete_phase(pending_phase.tasks.first())
        pending_phase.refresh_from_db()
        assert pending_phase.status == "pending"
        assert result is None

    def test_already_completed_phase_is_noop(self, workplan):
        completed_phase = PhaseFactory(
            name="Done Phase", workplan=workplan, status="completed"
        )
        make_task(completed_phase, "done")
        result = maybe_complete_phase(completed_phase.tasks.first())
        completed_phase.refresh_from_db()
        assert completed_phase.status == "completed"
        assert result is None

    def test_empty_phase_not_completed(self, workplan):
        empty_phase = PhaseFactory(
            name="Empty Phase", workplan=workplan, status="active"
        )
        # Create a task in a different phase so we have something to pass
        other_phase = PhaseFactory(workplan=workplan, status="active")
        task = make_task(other_phase, "done")
        # Manually point at empty phase to test the guard
        task.phase = empty_phase
        task.save()
        # Now the task is in the empty phase — but it's the only task and it's done
        # so this should complete. The real "empty" case is no tasks at all.
        # Let's test with a mock-like approach: remove the task again
        task.delete()
        # Create a dummy task in another phase
        dummy = make_task(other_phase, "done")
        dummy.phase = empty_phase
        # Don't save — so empty_phase has no tasks in DB
        result = maybe_complete_phase(dummy)
        # dummy.phase is empty_phase but dummy isn't saved with that phase
        # The function queries phase.tasks which goes to DB
        empty_phase.refresh_from_db()
        assert empty_phase.status == "active"
        assert result is None


# ---------------------------------------------------------------------------
# Integration tests: through API endpoints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAutoCompleteViaTaskComplete:
    def test_complete_auto_completes_phase(self, api_client, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "doing")
        response = api_client.post(f"/v1/tasks/{t2.id}/complete/")
        assert response.status_code == 200
        phase.refresh_from_db()
        assert phase.status == "completed"

    def test_complete_does_not_complete_phase_with_remaining(self, api_client, phase):
        t1 = make_task(phase, "todo")
        t2 = make_task(phase, "doing")
        response = api_client.post(f"/v1/tasks/{t2.id}/complete/")
        assert response.status_code == 200
        phase.refresh_from_db()
        assert phase.status == "active"


@pytest.mark.django_db
class TestAutoCompleteViaTaskCancel:
    def test_cancel_auto_completes_phase(self, api_client, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "todo")
        response = api_client.post(f"/v1/tasks/{t2.id}/cancel/")
        assert response.status_code == 200
        phase.refresh_from_db()
        assert phase.status == "completed"

    def test_cancel_does_not_complete_phase_with_remaining(self, api_client, phase):
        t1 = make_task(phase, "doing")
        t2 = make_task(phase, "todo")
        response = api_client.post(f"/v1/tasks/{t2.id}/cancel/")
        assert response.status_code == 200
        phase.refresh_from_db()
        assert phase.status == "active"


@pytest.mark.django_db
class TestAutoCompleteViaReviewApprove:
    def test_review_approve_auto_completes_phase(self, api_client, phase):
        t1 = make_task(phase, "done")
        t2 = make_task(phase, "pending_completion_review")
        response = api_client.post(
            f"/v1/tasks/{t2.id}/reviews/",
            {"decision": "approved", "reviewer_id": "human-1", "reviewer_type": "human"},
            format="json",
        )
        assert response.status_code == 201
        phase.refresh_from_db()
        assert phase.status == "completed"
