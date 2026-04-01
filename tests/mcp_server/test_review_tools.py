"""
Tests for the vtf_review_task MCP tool (P3.4).

Tests call the tool Python functions directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools._review_agent import vtf_review_task
from tests.factories import MilestoneFactory, ProjectFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# test_review_approve_start — pending_start_review → todo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_approve_start():
    """Approving a task in pending_start_review moves it to todo."""
    task = TaskFactory(status="pending_start_review")

    result = json.loads(vtf_review_task(task_id=task.id, decision="approved"))

    assert result["success"] is True
    assert result["data"]["task"]["status"] == "todo"
    assert result["data"]["task"]["previous_status"] == "pending_start_review"


# ---------------------------------------------------------------------------
# test_review_approve_completion — pending_completion_review → done
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_approve_completion():
    """Approving a task in pending_completion_review moves it to done."""
    task = TaskFactory(status="pending_completion_review")

    result = json.loads(vtf_review_task(task_id=task.id, decision="approved"))

    assert result["success"] is True
    assert result["data"]["task"]["status"] == "done"
    assert result["data"]["task"]["previous_status"] == "pending_completion_review"


# ---------------------------------------------------------------------------
# test_review_changes_requested — with reason
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_changes_requested():
    """changes_requested with a reason moves task to changes_requested status."""
    task = TaskFactory(status="pending_completion_review")

    result = json.loads(
        vtf_review_task(
            task_id=task.id,
            decision="changes_requested",
            reason="Missing unit tests for edge cases.",
        )
    )

    assert result["success"] is True
    assert result["data"]["task"]["status"] == "changes_requested"


# ---------------------------------------------------------------------------
# test_review_not_in_review_status_error — actionable error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_not_in_review_status_error():
    """Returns actionable error when task is not in a review status."""
    task = TaskFactory(status="doing")

    result = json.loads(vtf_review_task(task_id=task.id, decision="approved"))

    assert result["success"] is False
    assert result["message"] != ""
    assert "available_actions" in result
    assert len(result["available_actions"]) > 0


# ---------------------------------------------------------------------------
# test_review_includes_milestone_progress
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_includes_milestone_progress():
    """Response includes milestone_progress when task belongs to a milestone."""
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)
    milestone = MilestoneFactory(workplan=workplan)
    task = TaskFactory(
        project=project,
        milestone=milestone,
        workplan=workplan,
        status="pending_completion_review",
    )
    # Create another done task in the same milestone for non-zero progress
    TaskFactory(project=project, milestone=milestone, workplan=workplan, status="done")

    result = json.loads(vtf_review_task(task_id=task.id, decision="approved"))

    assert result["success"] is True
    assert result["data"]["milestone_progress"] is not None
    ms = result["data"]["milestone_progress"]
    assert ms["id"] == milestone.id
    assert "completed" in ms
    assert "total" in ms
    assert "pct" in ms


# ---------------------------------------------------------------------------
# Fuzzy decision suggestion tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_fuzzy_approve_suggests_approved():
    """vtf_review_task(decision='approve') suggests 'approved'."""
    task = TaskFactory(status="pending_completion_review")

    result = json.loads(vtf_review_task(task_id=task.id, decision="approve"))

    assert result["success"] is False
    assert "Did you mean 'approved'?" in result["message"]


@pytest.mark.django_db
def test_review_fuzzy_no_match_no_suggestion():
    """vtf_review_task(decision='frobnicate') gives no suggestion."""
    task = TaskFactory(status="pending_completion_review")

    result = json.loads(vtf_review_task(task_id=task.id, decision="frobnicate"))

    assert result["success"] is False
    assert "Did you mean" not in result["message"]


# ---------------------------------------------------------------------------
# Reviewer != claimer enforcement tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_review_rejected_when_reviewer_is_claimer():
    """vtf_review_task rejects when reviewer_id matches task.claimed_by."""
    task = TaskFactory(status="pending_completion_review", claimed_by="supervisor")

    result = json.loads(
        vtf_review_task(task_id=task.id, decision="approved", reviewer_id="supervisor")
    )

    assert result["success"] is False
    assert "same agent" in result["message"].lower()
    task.refresh_from_db()
    assert task.status == "pending_completion_review"  # unchanged


@pytest.mark.django_db
def test_review_accepted_when_reviewer_differs_from_claimer():
    """vtf_review_task succeeds when reviewer_id differs from claimed_by."""
    task = TaskFactory(status="pending_completion_review", claimed_by="supervisor")

    result = json.loads(
        vtf_review_task(task_id=task.id, decision="approved", reviewer_id="judge-abc")
    )

    assert result["success"] is True
    assert result["data"]["task"]["status"] == "done"


@pytest.mark.django_db
def test_review_allowed_when_no_claimer():
    """vtf_review_task succeeds when task has no claimed_by (e.g., imported tasks)."""
    task = TaskFactory(status="pending_completion_review", claimed_by=None)

    result = json.loads(
        vtf_review_task(task_id=task.id, decision="approved", reviewer_id="anyone")
    )

    assert result["success"] is True
    assert result["data"]["task"]["status"] == "done"
