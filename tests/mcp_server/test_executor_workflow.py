"""
End-to-end test for the complete executor workflow.

Exercises all 4 workflow tools in sequence:
    vtf_next_work → vtf_claim_and_start → vtf_report_progress → vtf_submit_work

Proves the full MCP tool chain works as an integrated workflow.
"""
import json

import pytest

from events.models import TaskEvent
from mcp_server.tools.workflow import (
    vtf_claim_and_start,
    vtf_next_work,
    vtf_report_progress,
    vtf_submit_work,
)
from tests.factories import AgentFactory, MilestoneFactory, ProjectFactory, TaskFactory, WorkplanFactory


@pytest.mark.django_db
def test_full_executor_workflow():
    """End-to-end: find work, claim it, report progress, submit."""
    # Setup: project, workplan, milestone, todo task with spec
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)
    milestone = MilestoneFactory(workplan=workplan)
    agent = AgentFactory(tags=["executor", "sonnet"])

    spec_text = (
        "description: Implement the feature\n"
        "files:\n"
        "  create:\n"
        "    - src/feature.py\n"
        "acceptance_criteria:\n"
        "  - Feature is implemented\n"
        "test_command:\n"
        "  unit: pytest tests/feature/ -v\n"
    )

    task = TaskFactory(
        project=project,
        workplan=workplan,
        milestone=milestone,
        status="todo",
        spec=spec_text,
        test_command={"unit": "pytest tests/feature/ -v"},
        needs_review_on_completion=False,
    )

    # ------------------------------------------------------------------
    # Step 1: vtf_next_work returns the task
    # ------------------------------------------------------------------
    next_result = json.loads(vtf_next_work(project_id=project.id))

    assert next_result["success"] is True
    assert next_result["data"] is not None
    assert next_result["data"]["task"]["id"] == task.id
    assert "spec_summary" in next_result["data"]
    assert "dependencies" in next_result["data"]
    assert "available_actions" in next_result
    assert len(next_result["available_actions"]) > 0

    # ------------------------------------------------------------------
    # Step 2: vtf_claim_and_start claims it, returns full context
    # ------------------------------------------------------------------
    claim_result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent.id))

    assert claim_result["success"] is True
    assert claim_result["data"]["task"]["id"] == task.id
    assert claim_result["data"]["task"]["status"] == "doing"
    assert claim_result["data"]["task"]["claimed_by"] == agent.id
    assert claim_result["data"]["spec"] == spec_text
    assert "dependencies" in claim_result["data"]
    assert "test_command" in claim_result["data"]
    assert claim_result["data"]["test_command"] == {"unit": "pytest tests/feature/ -v"}
    assert "available_actions" in claim_result
    assert any("report_progress" in a for a in claim_result["available_actions"])
    assert any("submit_work" in a for a in claim_result["available_actions"])

    # Verify claim events were recorded
    claimed_events = TaskEvent.objects.filter(task=task, event_type="claimed")
    assert claimed_events.exists(), "claimed event should be recorded after vtf_claim_and_start"

    status_changed_events = TaskEvent.objects.filter(
        task=task, event_type="status_changed", data__to="doing"
    )
    assert status_changed_events.exists(), "status_changed event (todo→doing) should be recorded"

    # ------------------------------------------------------------------
    # Step 3: vtf_report_progress extends claim + adds note
    # ------------------------------------------------------------------
    progress_note = "50% done — core logic implemented, writing tests"
    progress_result = json.loads(
        vtf_report_progress(task_id=task.id, note=progress_note, agent_id=agent.id)
    )

    assert progress_result["success"] is True
    assert progress_result["data"]["task_id"] == task.id
    assert "claim_expires_at" in progress_result["data"]
    assert progress_result["data"]["note_added"] is True

    # Verify the progress event was recorded
    progress_events = TaskEvent.objects.filter(task=task, event_type="progress_note")
    assert progress_events.exists(), "progress_note event should be recorded"
    assert progress_events.first().data.get("note") == progress_note

    # ------------------------------------------------------------------
    # Step 4: vtf_submit_work completes the task
    # ------------------------------------------------------------------
    completion_note = "Done — all tests pass, branch committed"
    submit_result = json.loads(
        vtf_submit_work(task_id=task.id, completion_note=completion_note, agent_id=agent.id)
    )

    assert submit_result["success"] is True
    assert submit_result["data"]["task"]["id"] == task.id

    final_status = submit_result["data"]["task"]["status"]
    assert final_status in ("done", "pending_completion_review"), (
        f"Task should end in done or pending_completion_review, got: {final_status}"
    )

    # For this task with needs_review_on_completion=False, should go to done
    assert final_status == "done"
    assert submit_result["data"]["review_required"] is False

    # Verify completion events were recorded
    completion_note_events = TaskEvent.objects.filter(task=task, event_type="completion_note")
    assert completion_note_events.exists(), "completion_note event should be recorded"
    assert completion_note_events.first().data.get("note") == completion_note

    final_status_events = TaskEvent.objects.filter(
        task=task, event_type="status_changed", data__to="done"
    )
    assert final_status_events.exists(), "status_changed event (doing→done) should be recorded"

    # ------------------------------------------------------------------
    # Overall lifecycle verification
    # ------------------------------------------------------------------
    # Task should now be in done state
    task.refresh_from_db()
    assert task.status == "done"

    # Verify all events are in the audit log (at least 3: todo→doing, claimed, doing→done)
    all_events = TaskEvent.objects.filter(task=task)
    assert all_events.count() >= 3, (
        f"Expected at least 3 events (status_changed×2, claimed, progress_note, completion_note), "
        f"got: {all_events.count()}"
    )
