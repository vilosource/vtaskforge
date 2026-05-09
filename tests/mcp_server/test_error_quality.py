"""
Parametrized error quality tests for all MCP tools (P4.1).

Verifies that every error path across all 9 MCP tools returns:
- success: False
- message: actionable (explains what went wrong and what to do)
- available_actions: non-empty list
- data: includes relevant context

Tools covered:
  - vtf_board_overview (no error paths — tool never fails)
  - vtf_next_work (no error paths — graceful success when empty)
  - vtf_search_tasks (no error paths — returns empty results)
  - vtf_claim_and_start (tag_mismatch, deps_unmet, ALREADY_CLAIMED, FORBIDDEN)
  - vtf_report_progress (not found, not doing)
  - vtf_submit_work (not found, not doing)
  - vtf_task_detail (not found)
  - vtf_manage_task (unknown action, create variants, update, transition, block, delete, assign, unassign)
  - vtf_review_task (invalid decision, missing reason, not in review status)
"""
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from mcp_server.tools.detail import vtf_task_detail
from mcp_server.tools.manage import vtf_manage_task
from mcp_server.tools._review_agent import vtf_review_task
from mcp_server.tools._workflow_agent import vtf_claim_and_start, vtf_report_progress, vtf_submit_work
from tests.factories import AgentFactory, LinkFactory, MilestoneFactory, ProjectFactory, TaskFactory, WorkplanFactory


@pytest.fixture
def agent1(db):
    """An Agent for claiming tasks in error quality tests."""
    return AgentFactory(name="error-test-agent", tags=[])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse(raw: str) -> dict:
    return json.loads(raw)


# ===========================================================================
# vtf_claim_and_start error paths
# ===========================================================================


@pytest.mark.django_db
def test_claim_tag_mismatch_error(agent1):
    """tag_mismatch: error is actionable and has available_actions."""
    task = TaskFactory(status="todo", required_tags=["python", "docker"])

    result = _parse(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id, tags="python"))

    assert result["success"] is False
    msg = result["message"].lower()
    assert "tag" in msg or "require" in msg
    assert len(result["available_actions"]) > 0
    assert result["data"]["task_id"] == task.id


@pytest.mark.django_db
def test_claim_deps_unmet_error(agent1):
    """deps_unmet: error names the blocking dependency and has available_actions."""
    blocker = TaskFactory(status="doing")
    task = TaskFactory(status="todo")
    LinkFactory(
        source_type="task",
        source_id=task.id,
        target_type="task",
        target_id=blocker.id,
        link_type="depends_on",
    )

    result = _parse(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

    assert result["success"] is False
    assert blocker.id in result["message"]
    assert len(result["available_actions"]) > 0
    assert "dependency_id" in result["data"]


@pytest.mark.django_db
def test_claim_already_claimed_error(agent1):
    """ALREADY_CLAIMED: error explains status and has available_actions."""
    task = TaskFactory(status="doing")

    result = _parse(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

    assert result["success"] is False
    msg = result["message"].lower()
    assert "doing" in msg or "status" in msg or "claim" in msg
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_claim_forbidden_error(agent1):
    """FORBIDDEN: error explains task is assigned to another agent, has available_actions."""
    other_agent = AgentFactory(name="other-agent")
    task = TaskFactory(status="todo", assigned_to=other_agent.user)

    result = _parse(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

    assert result["success"] is False
    msg = result["message"].lower()
    assert "agent" in msg or "assign" in msg or "forbidden" in msg
    assert len(result["available_actions"]) > 0


# ===========================================================================
# vtf_report_progress error paths
# ===========================================================================


@pytest.mark.django_db
def test_report_progress_not_found_error():
    """Task not found: error is actionable and has available_actions."""
    result = _parse(vtf_report_progress(task_id="nonexistent-id"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0
    assert result["data"]["task_id"] == "nonexistent-id"


@pytest.mark.django_db
def test_report_progress_not_doing_error():
    """Not doing status: error explains current status and what to do."""
    task = TaskFactory(status="todo")

    result = _parse(vtf_report_progress(task_id=task.id))

    assert result["success"] is False
    msg = result["message"].lower()
    assert "doing" in msg
    assert "todo" in msg or "status" in msg
    assert len(result["available_actions"]) > 0
    assert result["data"]["current_status"] == "todo"


# ===========================================================================
# vtf_submit_work error paths
# ===========================================================================


@pytest.mark.django_db
def test_submit_work_not_found_error():
    """Task not found: error is actionable and has available_actions."""
    result = _parse(vtf_submit_work(task_id="nonexistent-id"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0
    assert result["data"]["task_id"] == "nonexistent-id"


@pytest.mark.django_db
def test_submit_work_not_doing_error():
    """Not doing status: error explains current status and what to do."""
    task = TaskFactory(status="todo")

    result = _parse(vtf_submit_work(task_id=task.id))

    assert result["success"] is False
    msg = result["message"].lower()
    assert "doing" in msg
    assert "todo" in msg or "status" in msg
    assert len(result["available_actions"]) > 0
    assert result["data"]["current_status"] == "todo"


# ===========================================================================
# vtf_task_detail error paths
# ===========================================================================


@pytest.mark.django_db
def test_task_detail_not_found_error():
    """Task not found: error is actionable."""
    result = _parse(vtf_task_detail(task_id="nonexistent-id"))

    assert result["success"] is False
    assert "not found" in result["message"].lower()


# ===========================================================================
# vtf_manage_task error paths
# ===========================================================================


@pytest.mark.django_db
def test_manage_unknown_action_error():
    """Unknown action: error names the bad action and lists valid ones."""
    result = _parse(vtf_manage_task(action="frobnicate"))

    assert result["success"] is False
    assert "frobnicate" in result["message"]
    assert len(result["available_actions"]) > 0
    assert result["data"]["action"] == "frobnicate"


@pytest.mark.django_db
def test_manage_create_missing_title_error():
    """create missing title: error says title is required, has available_actions."""
    project = ProjectFactory()

    result = _parse(vtf_manage_task(action="create", project_id=project.id))

    assert result["success"] is False
    assert "title" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_create_missing_project_id_error():
    """create missing project_id: error says project_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="create", title="My Task"))

    assert result["success"] is False
    assert "project_id" in result["message"].lower() or "project" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_create_project_not_found_error():
    """create with invalid project_id: error is actionable and has available_actions."""
    result = _parse(vtf_manage_task(
        action="create",
        title="My Task",
        project_id="nonexistent-project",
    ))

    assert result["success"] is False
    assert "nonexistent-project" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0
    assert result["data"]["project_id"] == "nonexistent-project"


@pytest.mark.django_db
def test_manage_update_missing_task_id_error():
    """update missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="update", title="New Title"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_update_task_not_found_error():
    """update with invalid task_id: error is actionable and has available_actions."""
    result = _parse(vtf_manage_task(action="update", task_id="nonexistent-id", title="New Title"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_submit_missing_task_id_error():
    """submit missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="submit"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_submit_task_not_found_error():
    """submit with invalid task_id: error is actionable and has available_actions."""
    result = _parse(vtf_manage_task(action="submit", task_id="nonexistent-id"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_submit_invalid_transition_error():
    """submit from a non-draft status: error explains current status and valid transitions."""
    task = TaskFactory(status="done")

    result = _parse(vtf_manage_task(action="submit", task_id=task.id))

    assert result["success"] is False
    assert "done" in result["message"].lower() or "transition" in result["message"].lower()
    assert len(result["available_actions"]) > 0
    assert "current_status" in result["data"]
    assert "valid_transitions" in result["data"]


@pytest.mark.django_db
def test_manage_block_missing_task_id_error():
    """block missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="block"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_block_task_not_found_error():
    """block with invalid task_id: error is actionable and has available_actions."""
    result = _parse(vtf_manage_task(action="block", task_id="nonexistent-id"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_block_invalid_transition_error():
    """block from terminal status: error explains terminal state, has available_actions."""
    task = TaskFactory(status="done")

    result = _parse(vtf_manage_task(action="block", task_id=task.id))

    assert result["success"] is False
    assert "done" in result["message"].lower() or "terminal" in result["message"].lower() or "transition" in result["message"].lower()
    assert len(result["available_actions"]) > 0
    assert "current_status" in result["data"]


@pytest.mark.django_db
def test_manage_delete_missing_task_id_error():
    """delete missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="delete"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_delete_task_not_found_error():
    """delete with invalid task_id: error is actionable and has available_actions."""
    result = _parse(vtf_manage_task(action="delete", task_id="nonexistent-id"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_assign_missing_task_id_error():
    """assign missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="assign", assigned_to="agent-1"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_assign_missing_assigned_to_error():
    """assign missing assigned_to: error says assigned_to is required, has available_actions."""
    task = TaskFactory(status="todo")

    result = _parse(vtf_manage_task(action="assign", task_id=task.id))

    assert result["success"] is False
    assert "assigned_to" in result["message"].lower()
    assert len(result["available_actions"]) > 0
    assert result["data"]["task_id"] == task.id


@pytest.mark.django_db
def test_manage_assign_task_not_found_error():
    """assign with invalid task_id: error is actionable and has available_actions."""
    result = _parse(vtf_manage_task(action="assign", task_id="nonexistent-id", assigned_to="agent-1"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_unassign_missing_task_id_error():
    """unassign missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="unassign"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_unassign_task_not_found_error():
    """unassign with invalid task_id: error is actionable and has available_actions."""
    result = _parse(vtf_manage_task(action="unassign", task_id="nonexistent-id"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_defer_missing_task_id_error():
    """defer missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="defer"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_cancel_missing_task_id_error():
    """cancel missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="cancel"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_manage_unblock_missing_task_id_error():
    """unblock missing task_id: error says task_id is required, has available_actions."""
    result = _parse(vtf_manage_task(action="unblock"))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()
    assert len(result["available_actions"]) > 0


# ===========================================================================
# vtf_review_task error paths
# ===========================================================================


@pytest.mark.django_db
def test_review_invalid_decision_error():
    """Invalid decision: error names bad value and lists valid options, has available_actions."""
    task = TaskFactory(status="pending_completion_review")

    result = _parse(vtf_review_task(task_id=task.id, decision="maybe"))

    assert result["success"] is False
    assert "maybe" in result["message"]
    assert len(result["available_actions"]) > 0
    assert result["data"]["decision"] == "maybe"


@pytest.mark.django_db
@pytest.mark.parametrize("decision", ["changes_requested", "rejected"])
def test_review_missing_reason_error(decision):
    """changes_requested/rejected without reason: error explains requirement, has available_actions."""
    task = TaskFactory(status="pending_completion_review")

    result = _parse(vtf_review_task(task_id=task.id, decision=decision))

    assert result["success"] is False
    assert "reason" in result["message"].lower()
    assert len(result["available_actions"]) > 0
    assert result["data"]["decision"] == decision


@pytest.mark.django_db
def test_review_task_not_in_review_status_error():
    """Task not in review status: error explains which statuses support review, has available_actions."""
    task = TaskFactory(status="doing")

    result = _parse(vtf_review_task(task_id=task.id, decision="approved"))

    assert result["success"] is False
    assert result["message"] != ""
    assert "review" in result["message"].lower() or "pending" in result["message"].lower() or "doing" in result["message"].lower()
    assert len(result["available_actions"]) > 0


@pytest.mark.django_db
def test_review_task_not_found_error():
    """Task not found: error via ReviewError is actionable and has available_actions."""
    result = _parse(vtf_review_task(task_id="nonexistent-id", decision="approved"))

    assert result["success"] is False
    assert "nonexistent-id" in result["message"] or "not found" in result["message"].lower()
    assert len(result["available_actions"]) > 0
