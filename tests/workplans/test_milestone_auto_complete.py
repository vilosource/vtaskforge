"""
Tests for automatic milestone completion when all tasks reach terminal status.
"""
import pytest

from tests.factories import MilestoneFactory, TaskFactory, WorkplanFactory, AgentFactory

from workplans.completion import maybe_complete_milestone


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def milestone(db, workplan):
    return MilestoneFactory(name="Test Milestone", workplan=workplan, status="active")


def make_task(milestone, status="draft"):
    return TaskFactory(
        title="Test Task",
        milestone=milestone,
        workplan=milestone.workplan,
        status=status,
    )


# ---------------------------------------------------------------------------
# Unit tests: maybe_complete_milestone
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMaybeCompleteMilestoneAllDone:
    def test_completes_milestone_when_all_done(self, milestone):
        t1 = make_task(milestone, "done")
        t2 = make_task(milestone, "done")
        result = maybe_complete_milestone(t1)
        milestone.refresh_from_db()
        assert milestone.status == "completed"

    def test_returns_milestone_when_completed(self, milestone):
        t1 = make_task(milestone, "done")
        result = maybe_complete_milestone(t1)
        assert result == milestone


@pytest.mark.django_db
class TestMaybeCompleteMilestoneTerminalMix:
    def test_completes_with_done_and_cancelled(self, milestone):
        t1 = make_task(milestone, "done")
        t2 = make_task(milestone, "cancelled")
        result = maybe_complete_milestone(t1)
        milestone.refresh_from_db()
        assert milestone.status == "completed"

    def test_completes_with_all_cancelled(self, milestone):
        t1 = make_task(milestone, "cancelled")
        t2 = make_task(milestone, "cancelled")
        result = maybe_complete_milestone(t1)
        milestone.refresh_from_db()
        assert milestone.status == "completed"


@pytest.mark.django_db
class TestMaybeCompleteMilestoneNonTerminalRemain:
    def test_does_not_complete_with_todo_remaining(self, milestone):
        t1 = make_task(milestone, "done")
        t2 = make_task(milestone, "todo")
        result = maybe_complete_milestone(t1)
        milestone.refresh_from_db()
        assert milestone.status == "active"

    def test_returns_none_when_not_completed(self, milestone):
        t1 = make_task(milestone, "done")
        t2 = make_task(milestone, "doing")
        result = maybe_complete_milestone(t1)
        assert result is None

    def test_does_not_complete_with_draft_remaining(self, milestone):
        t1 = make_task(milestone, "done")
        t2 = make_task(milestone, "draft")
        result = maybe_complete_milestone(t1)
        milestone.refresh_from_db()
        assert milestone.status == "active"


@pytest.mark.django_db
class TestMaybeCompleteMilestoneGuards:
    def test_pending_milestone_not_completed(self, workplan):
        pending_milestone = MilestoneFactory(
            name="Pending Milestone", workplan=workplan, status="pending"
        )
        make_task(pending_milestone, "done")
        result = maybe_complete_milestone(pending_milestone.tasks.first())
        pending_milestone.refresh_from_db()
        assert pending_milestone.status == "pending"
        assert result is None

    def test_already_completed_milestone_is_noop(self, workplan):
        completed_milestone = MilestoneFactory(
            name="Done Milestone", workplan=workplan, status="completed"
        )
        make_task(completed_milestone, "done")
        result = maybe_complete_milestone(completed_milestone.tasks.first())
        completed_milestone.refresh_from_db()
        assert completed_milestone.status == "completed"
        assert result is None

    def test_empty_milestone_not_completed(self, workplan):
        empty_milestone = MilestoneFactory(
            name="Empty Milestone", workplan=workplan, status="active"
        )
        # Create a task in a different milestone so we have something to pass
        other_milestone = MilestoneFactory(workplan=workplan, status="active")
        task = make_task(other_milestone, "done")
        # Manually point at empty milestone to test the guard
        task.milestone = empty_milestone
        task.save()
        # Now the task is in the empty milestone — but it's the only task and it's done
        # so this should complete. The real "empty" case is no tasks at all.
        # Let's test with a mock-like approach: remove the task again
        task.delete()
        # Create a dummy task in another milestone
        dummy = make_task(other_milestone, "done")
        dummy.milestone = empty_milestone
        # Don't save — so empty_milestone has no tasks in DB
        result = maybe_complete_milestone(dummy)
        # dummy.milestone is empty_milestone but dummy isn't saved with that milestone
        # The function queries milestone.tasks which goes to DB
        empty_milestone.refresh_from_db()
        assert empty_milestone.status == "active"
        assert result is None


# ---------------------------------------------------------------------------
# Integration tests: through API endpoints
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAutoCompleteViaTaskComplete:
    def test_complete_auto_completes_milestone(self, api_client, milestone):
        t1 = make_task(milestone, "done")
        t2 = TaskFactory(
            title="Test Task",
            milestone=milestone,
            workplan=milestone.workplan,
            status="doing",
            needs_review_on_completion=False
        )
        response = api_client.post(f"/v1/tasks/{t2.id}/complete/")
        assert response.status_code == 200
        milestone.refresh_from_db()
        assert milestone.status == "completed"

    def test_complete_does_not_complete_milestone_with_remaining(self, api_client, milestone):
        t1 = make_task(milestone, "todo")
        t2 = make_task(milestone, "doing")
        response = api_client.post(f"/v1/tasks/{t2.id}/complete/")
        assert response.status_code == 200
        milestone.refresh_from_db()
        assert milestone.status == "active"


@pytest.mark.django_db
class TestAutoCompleteViaTaskCancel:
    def test_cancel_auto_completes_milestone(self, api_client, milestone):
        t1 = make_task(milestone, "done")
        t2 = make_task(milestone, "todo")
        response = api_client.post(f"/v1/tasks/{t2.id}/cancel/")
        assert response.status_code == 200
        milestone.refresh_from_db()
        assert milestone.status == "completed"

    def test_cancel_does_not_complete_milestone_with_remaining(self, api_client, milestone):
        t1 = make_task(milestone, "doing")
        t2 = make_task(milestone, "todo")
        response = api_client.post(f"/v1/tasks/{t2.id}/cancel/")
        assert response.status_code == 200
        milestone.refresh_from_db()
        assert milestone.status == "active"


@pytest.mark.django_db
class TestAutoCompleteViaReviewApprove:
    def test_review_approve_auto_completes_milestone(self, api_client, milestone):
        t1 = make_task(milestone, "done")
        t2 = make_task(milestone, "pending_completion_review")
        response = api_client.post(
            f"/v1/tasks/{t2.id}/reviews/",
            {"decision": "approved", "reviewer_id": "human-1", "reviewer_type": "human"},
            format="json",
        )
        assert response.status_code == 201
        milestone.refresh_from_db()
        assert milestone.status == "completed"
