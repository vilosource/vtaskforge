"""
Tests for Task lifecycle action endpoints.

Tests both valid transitions and the 422 INVALID_TRANSITION error format.
"""
import pytest
from rest_framework import status

from tests.factories import AgentFactory, MilestoneFactory, TaskFactory, WorkplanFactory


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
def agent_abc(db):
    return AgentFactory(name="Agent ABC", tags=[])


def make_task(milestone, workplan, task_status="draft", **kwargs):
    return TaskFactory(
        title="Test Task",
        milestone=milestone,
        workplan=workplan,
        status=task_status,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Error format helper
# ---------------------------------------------------------------------------

def assert_invalid_transition_error(response, current_status, requested_status):
    """Assert that a 422 response has the standard INVALID_TRANSITION format."""
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    error = response.data["error"]
    assert error["code"] == "INVALID_TRANSITION"
    assert "message" in error
    details = error["details"]
    assert details["current_status"] == current_status
    assert details["requested_status"] == requested_status
    assert "valid_transitions" in details


# ---------------------------------------------------------------------------
# submit: draft -> todo
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSubmit:
    def test_submit_draft_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK

    def test_submit_draft_transitions_to_todo(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.data["status"] == "todo"

    def test_submit_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        api_client.post(f"/v1/tasks/{task.id}/submit/")
        task.refresh_from_db()
        assert task.status == "todo"

    def test_submit_from_todo_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert_invalid_transition_error(response, "todo", "todo")

    def test_submit_from_done_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert_invalid_transition_error(response, "done", "todo")

    def test_submit_from_cancelled_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "cancelled")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert_invalid_transition_error(response, "cancelled", "todo")

    def test_submit_blocked_when_milestone_pending(self, api_client, workplan):
        pending_milestone = MilestoneFactory(name="Pending", workplan=workplan, status="pending")
        task = make_task(pending_milestone, workplan)
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "GUARD_VIOLATION"
        assert "milestone" in response.data["error"]["message"].lower()

    def test_submit_blocked_when_milestone_completed(self, api_client, workplan):
        completed_milestone = MilestoneFactory(name="Done", workplan=workplan, status="completed")
        task = make_task(completed_milestone, workplan)
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "GUARD_VIOLATION"

    def test_submit_allowed_when_milestone_active(self, api_client, workplan):
        active_milestone = MilestoneFactory(name="Active", workplan=workplan, status="active")
        task = make_task(active_milestone, workplan)
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "todo"

    def test_submit_allowed_when_no_milestone(self, api_client, workplan):
        """Tasks with a workplan but no milestone can be submitted."""
        task = TaskFactory(
            title="No Milestone Task",
            workplan=workplan,
            milestone=None,
            project=workplan.project,
            status="draft",
        )
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_200_OK

    def test_submit_without_workplan_blocked(self, api_client, workplan):
        """Tasks without a workplan cannot be submitted."""
        task = TaskFactory(
            title="Backlog Task",
            workplan=None,
            milestone=None,
            project=workplan.project,
            status="draft",
        )
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "GUARD_VIOLATION"
        assert "workplan" in response.data["error"]["message"].lower()


# ---------------------------------------------------------------------------
# claim: todo -> doing
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestClaim:
    def test_claim_todo_returns_200(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_claim_transitions_to_doing(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.data["status"] == "doing"

    def test_claim_sets_claimed_by(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.data["claimed_by"] == agent_abc.id

    def test_claim_sets_claimed_at(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.data["claimed_at"] is not None

    def test_claim_sets_claim_expires_at(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.data["claim_expires_at"] is not None

    def test_claim_persists_to_db(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "todo")
        api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        task.refresh_from_db()
        assert task.status == "doing"
        assert task.claimed_by == agent_abc.id
        assert task.claimed_at is not None
        assert task.claim_expires_at is not None

    def test_claim_without_agent_id_returns_400(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_claim_from_draft_returns_409(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "ALREADY_CLAIMED"

    def test_claim_from_doing_returns_409(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "ALREADY_CLAIMED"

    def test_claim_from_done_returns_409(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {"agent_id": agent_abc.id}, format="json")
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "ALREADY_CLAIMED"


# ---------------------------------------------------------------------------
# unclaim: doing -> todo
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUnclaim:
    def test_unclaim_doing_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing", claimed_by="agent-1")
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert response.status_code == status.HTTP_200_OK

    def test_unclaim_transitions_to_todo(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing", claimed_by="agent-1")
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert response.data["status"] == "todo"

    def test_unclaim_clears_claimed_by(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing", claimed_by="agent-1")
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert response.data["claimed_by"] is None

    def test_unclaim_clears_claimed_at(self, api_client, milestone, workplan):
        from django.utils import timezone
        task = make_task(milestone, workplan, "doing", claimed_by="agent-1", claimed_at=timezone.now())
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert response.data["claimed_at"] is None

    def test_unclaim_clears_claim_expires_at(self, api_client, milestone, workplan):
        from django.utils import timezone
        task = make_task(milestone, workplan, "doing", claimed_by="agent-1", claim_expires_at=timezone.now())
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert response.data["claim_expires_at"] is None

    def test_unclaim_persists_to_db(self, api_client, milestone, workplan):
        from django.utils import timezone
        task = make_task(
            milestone, workplan, "doing",
            claimed_by="agent-1",
            claimed_at=timezone.now(),
            claim_expires_at=timezone.now(),
        )
        api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        task.refresh_from_db()
        assert task.status == "todo"
        assert task.claimed_by is None
        assert task.claimed_at is None
        assert task.claim_expires_at is None

    def test_unclaim_from_todo_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert_invalid_transition_error(response, "todo", "todo")

    def test_unclaim_from_draft_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/unclaim/")
        assert_invalid_transition_error(response, "draft", "todo")


# ---------------------------------------------------------------------------
# complete: doing -> done
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestComplete:
    def test_complete_doing_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing", needs_review_on_completion=False)
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.status_code == status.HTTP_200_OK

    def test_complete_transitions_to_done(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing", needs_review_on_completion=False)
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert response.data["status"] == "done"

    def test_complete_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing", needs_review_on_completion=False)
        api_client.post(f"/v1/tasks/{task.id}/complete/")
        task.refresh_from_db()
        assert task.status == "done"

    def test_complete_from_draft_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft", needs_review_on_completion=False)
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert_invalid_transition_error(response, "draft", "done")

    def test_complete_from_todo_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo", needs_review_on_completion=False)
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert_invalid_transition_error(response, "todo", "done")

    def test_complete_from_done_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done", needs_review_on_completion=False)
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert_invalid_transition_error(response, "done", "done")

    def test_complete_from_cancelled_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "cancelled", needs_review_on_completion=False)
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        assert_invalid_transition_error(response, "cancelled", "done")


# ---------------------------------------------------------------------------
# fail: doing -> needs_attention
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestFail:
    def test_fail_doing_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/fail/")
        assert response.status_code == status.HTTP_200_OK

    def test_fail_transitions_to_needs_attention(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/fail/")
        assert response.data["status"] == "needs_attention"

    def test_fail_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        api_client.post(f"/v1/tasks/{task.id}/fail/")
        task.refresh_from_db()
        assert task.status == "needs_attention"

    def test_fail_from_todo_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/fail/")
        assert_invalid_transition_error(response, "todo", "needs_attention")

    def test_fail_from_done_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/fail/")
        assert_invalid_transition_error(response, "done", "needs_attention")

    def test_fail_clears_claimed_by(self, api_client, milestone, workplan, agent_abc):
        task = make_task(milestone, workplan, "doing", claimed_by=agent_abc)
        api_client.post(f"/v1/tasks/{task.id}/fail/")
        task.refresh_from_db()
        assert task.claimed_by is None

    def test_fail_clears_claimed_at(self, api_client, milestone, workplan, agent_abc):
        from django.utils import timezone
        task = make_task(milestone, workplan, "doing", claimed_by=agent_abc, claimed_at=timezone.now())
        api_client.post(f"/v1/tasks/{task.id}/fail/")
        task.refresh_from_db()
        assert task.claimed_at is None

    def test_fail_clears_claim_expires_at(self, api_client, milestone, workplan, agent_abc):
        from django.utils import timezone
        task = make_task(
            milestone, workplan, "doing",
            claimed_by=agent_abc,
            claimed_at=timezone.now(),
            claim_expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )
        api_client.post(f"/v1/tasks/{task.id}/fail/")
        task.refresh_from_db()
        assert task.claim_expires_at is None


# ---------------------------------------------------------------------------
# resubmit: changes_requested -> review_return_to
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestResubmit:
    def test_resubmit_returns_200(self, api_client, milestone, workplan):
        task = make_task(
            milestone, workplan, "changes_requested",
            review_return_to="pending_start_review",
        )
        response = api_client.post(f"/v1/tasks/{task.id}/resubmit/")
        assert response.status_code == status.HTTP_200_OK

    def test_resubmit_transitions_to_review_return_to(self, api_client, milestone, workplan):
        task = make_task(
            milestone, workplan, "changes_requested",
            review_return_to="pending_start_review",
        )
        response = api_client.post(f"/v1/tasks/{task.id}/resubmit/")
        assert response.data["status"] == "pending_start_review"

    def test_resubmit_to_pending_completion_review(self, api_client, milestone, workplan):
        task = make_task(
            milestone, workplan, "changes_requested",
            review_return_to="pending_completion_review",
        )
        response = api_client.post(f"/v1/tasks/{task.id}/resubmit/")
        assert response.data["status"] == "pending_completion_review"

    def test_resubmit_without_review_return_to_returns_400(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "changes_requested")
        response = api_client.post(f"/v1/tasks/{task.id}/resubmit/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_resubmit_from_wrong_status_returns_422(self, api_client, milestone, workplan):
        task = make_task(
            milestone, workplan, "todo",
            review_return_to="pending_start_review",
        )
        response = api_client.post(f"/v1/tasks/{task.id}/resubmit/")
        assert_invalid_transition_error(response, "todo", "pending_start_review")

    def test_resubmit_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(
            milestone, workplan, "changes_requested",
            review_return_to="pending_start_review",
        )
        api_client.post(f"/v1/tasks/{task.id}/resubmit/")
        task.refresh_from_db()
        assert task.status == "pending_start_review"


# ---------------------------------------------------------------------------
# block: todo/doing -> blocked
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBlock:
    def test_block_from_todo_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/block/")
        assert response.status_code == status.HTTP_200_OK

    def test_block_from_todo_transitions_to_blocked(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/block/")
        assert response.data["status"] == "blocked"

    def test_block_from_doing_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/block/")
        assert response.status_code == status.HTTP_200_OK

    def test_block_from_doing_transitions_to_blocked(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/block/")
        assert response.data["status"] == "blocked"

    def test_block_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        api_client.post(f"/v1/tasks/{task.id}/block/")
        task.refresh_from_db()
        assert task.status == "blocked"

    def test_block_from_draft_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/block/")
        assert_invalid_transition_error(response, "draft", "blocked")

    def test_block_from_done_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/block/")
        assert_invalid_transition_error(response, "done", "blocked")


# ---------------------------------------------------------------------------
# unblock: blocked -> todo
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUnblock:
    def test_unblock_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "blocked")
        response = api_client.post(f"/v1/tasks/{task.id}/unblock/")
        assert response.status_code == status.HTTP_200_OK

    def test_unblock_transitions_to_todo(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "blocked")
        response = api_client.post(f"/v1/tasks/{task.id}/unblock/")
        assert response.data["status"] == "todo"

    def test_unblock_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "blocked")
        api_client.post(f"/v1/tasks/{task.id}/unblock/")
        task.refresh_from_db()
        assert task.status == "todo"

    def test_unblock_from_todo_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/unblock/")
        assert_invalid_transition_error(response, "todo", "todo")

    def test_unblock_from_done_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/unblock/")
        assert_invalid_transition_error(response, "done", "todo")


# ---------------------------------------------------------------------------
# defer: any non-terminal -> deferred
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDefer:
    def test_defer_from_draft_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/defer/")
        assert response.status_code == status.HTTP_200_OK

    def test_defer_from_todo_transitions_to_deferred(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/defer/")
        assert response.data["status"] == "deferred"

    def test_defer_from_doing_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/defer/")
        assert response.status_code == status.HTTP_200_OK

    def test_defer_from_blocked_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "blocked")
        response = api_client.post(f"/v1/tasks/{task.id}/defer/")
        assert response.status_code == status.HTTP_200_OK

    def test_defer_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        api_client.post(f"/v1/tasks/{task.id}/defer/")
        task.refresh_from_db()
        assert task.status == "deferred"

    def test_defer_from_done_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/defer/")
        assert_invalid_transition_error(response, "done", "deferred")

    def test_defer_from_cancelled_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "cancelled")
        response = api_client.post(f"/v1/tasks/{task.id}/defer/")
        assert_invalid_transition_error(response, "cancelled", "deferred")

    def test_defer_from_deferred_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "deferred")
        response = api_client.post(f"/v1/tasks/{task.id}/defer/")
        assert_invalid_transition_error(response, "deferred", "deferred")


# ---------------------------------------------------------------------------
# cancel: any non-terminal -> cancelled
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCancel:
    def test_cancel_from_draft_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/cancel/")
        assert response.status_code == status.HTTP_200_OK

    def test_cancel_transitions_to_cancelled(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/cancel/")
        assert response.data["status"] == "cancelled"

    def test_cancel_from_doing_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/cancel/")
        assert response.status_code == status.HTTP_200_OK

    def test_cancel_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        api_client.post(f"/v1/tasks/{task.id}/cancel/")
        task.refresh_from_db()
        assert task.status == "cancelled"

    def test_cancel_from_done_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/cancel/")
        assert_invalid_transition_error(response, "done", "cancelled")

    def test_cancel_from_cancelled_returns_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "cancelled")
        response = api_client.post(f"/v1/tasks/{task.id}/cancel/")
        assert_invalid_transition_error(response, "cancelled", "cancelled")


# ---------------------------------------------------------------------------
# heartbeat: extends claim_expires_at on doing task
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestHeartbeat:
    def test_heartbeat_doing_returns_200(self, api_client, milestone, workplan):
        from django.utils import timezone
        task = make_task(
            milestone, workplan, "doing",
            claimed_by="agent-1",
            claim_expires_at=timezone.now(),
        )
        response = api_client.post(f"/v1/tasks/{task.id}/heartbeat/")
        assert response.status_code == status.HTTP_200_OK

    def test_heartbeat_extends_claim_expires_at(self, api_client, milestone, workplan):
        from django.utils import timezone
        old_expiry = timezone.now()
        task = make_task(
            milestone, workplan, "doing",
            claimed_by="agent-1",
            claim_expires_at=old_expiry,
        )
        response = api_client.post(f"/v1/tasks/{task.id}/heartbeat/")
        assert response.status_code == status.HTTP_200_OK
        task.refresh_from_db()
        assert task.claim_expires_at > old_expiry

    def test_heartbeat_non_doing_returns_400(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/heartbeat/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_heartbeat_draft_returns_400(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(f"/v1/tasks/{task.id}/heartbeat/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_heartbeat_done_returns_400(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/heartbeat/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_heartbeat_persists_to_db(self, api_client, milestone, workplan):
        from django.utils import timezone
        old_expiry = timezone.now()
        task = make_task(
            milestone, workplan, "doing",
            claimed_by="agent-1",
            claim_expires_at=old_expiry,
        )
        api_client.post(f"/v1/tasks/{task.id}/heartbeat/")
        task.refresh_from_db()
        assert task.claim_expires_at > old_expiry


# ---------------------------------------------------------------------------
# progress: placeholder
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProgress:
    def test_progress_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(
            f"/v1/tasks/{task.id}/progress/",
            {"message": "Working on it"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_progress_works_on_any_status(self, api_client, milestone, workplan):
        for task_status in ["draft", "todo", "doing", "blocked", "deferred"]:
            task = make_task(milestone, workplan, task_status)
            response = api_client.post(f"/v1/tasks/{task.id}/progress/", {"message": "msg"}, format="json")
            assert response.status_code == status.HTTP_200_OK

    def test_progress_returns_task_data(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(f"/v1/tasks/{task.id}/progress/", {"message": "msg"}, format="json")
        assert response.data["id"] == task.id


# ---------------------------------------------------------------------------
# assign/unassign
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAssign:
    def test_assign_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/assign/", {"assigned_to": "agent-x"}, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_assign_sets_assigned_to(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/assign/", {"assigned_to": "agent-x"}, format="json")
        assert response.data["assigned_to"] == "agent-x"

    def test_assign_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        api_client.post(f"/v1/tasks/{task.id}/assign/", {"assigned_to": "agent-x"}, format="json")
        task.refresh_from_db()
        assert task.assigned_to == "agent-x"

    def test_assign_without_assigned_to_returns_400(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/assign/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_assign_works_on_any_status(self, api_client, milestone, workplan):
        for task_status in ["draft", "todo", "doing", "blocked"]:
            task = make_task(milestone, workplan, task_status)
            response = api_client.post(f"/v1/tasks/{task.id}/assign/", {"assigned_to": "agent-x"}, format="json")
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestUnassign:
    def test_unassign_returns_200(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo", assigned_to="agent-x")
        response = api_client.post(f"/v1/tasks/{task.id}/unassign/")
        assert response.status_code == status.HTTP_200_OK

    def test_unassign_clears_assigned_to(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo", assigned_to="agent-x")
        response = api_client.post(f"/v1/tasks/{task.id}/unassign/")
        assert response.data["assigned_to"] is None

    def test_unassign_persists_to_db(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo", assigned_to="agent-x")
        api_client.post(f"/v1/tasks/{task.id}/unassign/")
        task.refresh_from_db()
        assert task.assigned_to is None

    def test_unassign_works_on_unassigned_task(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/unassign/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["assigned_to"] is None


# ---------------------------------------------------------------------------
# Error format verification
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInvalidTransitionErrorFormat:
    def test_error_has_code_key(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert "error" in response.data
        assert response.data["error"]["code"] == "INVALID_TRANSITION"

    def test_error_has_message_key(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert "message" in response.data["error"]

    def test_error_has_details_with_statuses(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        details = response.data["error"]["details"]
        assert details["current_status"] == "done"
        assert details["requested_status"] == "todo"

    def test_error_has_valid_transitions_list(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "todo")
        response = api_client.post(f"/v1/tasks/{task.id}/complete/")
        details = response.data["error"]["details"]
        assert "valid_transitions" in details
        assert isinstance(details["valid_transitions"], list)

    def test_error_valid_transitions_is_empty_for_terminal(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/cancel/")
        details = response.data["error"]["details"]
        assert details["valid_transitions"] == []

    def test_error_status_code_is_422(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(f"/v1/tasks/{task.id}/submit/")
        assert response.status_code == 422
