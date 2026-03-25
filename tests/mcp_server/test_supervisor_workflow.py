"""
End-to-end tests for the supervisor and judge workflows.

Exercises the board overview → search → detail → review cycle and the
manage task lifecycle. Proves the full MCP tool chain works for non-executor roles.
"""
import json

import pytest

from events.models import TaskEvent
from mcp_server.tools.board import vtf_board_overview
from mcp_server.tools.detail import vtf_task_detail
from mcp_server.tools.manage import vtf_manage_task
from mcp_server.tools.review import vtf_review_task
from mcp_server.tools.search import vtf_search_tasks
from tests.factories import MilestoneFactory, ProjectFactory, TaskFactory, WorkplanFactory


@pytest.mark.django_db
def test_supervisor_board_to_review_workflow():
    """Supervisor checks board, finds pending review, reviews it."""
    # Setup: project with workplan, milestone, and a task in pending_completion_review
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)
    milestone = MilestoneFactory(workplan=workplan)

    # Create a task directly in pending_completion_review status
    task = TaskFactory(
        project=project,
        workplan=workplan,
        milestone=milestone,
        status="pending_completion_review",
        title="Feature implementation task",
    )

    # Also create some other tasks to make the board more realistic
    TaskFactory(project=project, workplan=workplan, milestone=milestone, status="todo")
    TaskFactory(project=project, workplan=workplan, milestone=milestone, status="doing")

    # ------------------------------------------------------------------
    # Step 1: vtf_board_overview — supervisor checks the board
    # ------------------------------------------------------------------
    board_result = json.loads(vtf_board_overview(project_id=project.id))

    assert board_result["success"] is True
    board_data = board_result["data"]

    # Board should show counts including our pending_completion_review task
    assert "counts" in board_data
    assert "pending_reviews" in board_data
    assert board_data["counts"].get("pending_completion_review", 0) > 0, (
        "Board should show at least 1 pending_completion_review task"
    )

    # pending_reviews list should contain our task
    pending_review_ids = [t["id"] for t in board_data["pending_reviews"]]
    assert task.id in pending_review_ids, (
        f"Task {task.id} should appear in pending_reviews"
    )

    # ------------------------------------------------------------------
    # Step 2: vtf_search_tasks — find tasks pending completion review
    # ------------------------------------------------------------------
    search_result = json.loads(
        vtf_search_tasks(status="pending_completion_review", project_id=project.id)
    )

    assert search_result["success"] is True
    search_data = search_result["data"]
    assert search_data["total_count"] >= 1, "Search should find at least 1 pending review task"

    found_task_ids = [t["id"] for t in search_data["tasks"]]
    assert task.id in found_task_ids, (
        f"Task {task.id} should appear in search results"
    )

    # Each task in results should have available_actions
    for t in search_data["tasks"]:
        assert "available_actions" in t

    # ------------------------------------------------------------------
    # Step 3: vtf_task_detail — supervisor gets full context before reviewing
    # ------------------------------------------------------------------
    detail_result = json.loads(vtf_task_detail(task_id=task.id))

    assert detail_result["success"] is True
    detail_data = detail_result["data"]

    # Should include all context fields
    assert detail_data["task"]["id"] == task.id
    assert detail_data["task"]["status"] == "pending_completion_review"
    assert "spec" in detail_data
    assert "dependencies" in detail_data
    assert "reviews" in detail_data
    assert "recent_events" in detail_data

    # Message should indicate the task is awaiting completion review
    assert "pending_completion_review" in detail_result["message"].lower() or \
           "awaiting" in detail_result["message"].lower() or \
           "completion review" in detail_result["message"].lower(), (
        f"Message should indicate pending completion review, got: {detail_result['message']}"
    )

    # ------------------------------------------------------------------
    # Step 4: vtf_review_task — supervisor approves the task
    # ------------------------------------------------------------------
    review_result = json.loads(
        vtf_review_task(
            task_id=task.id,
            decision="approved",
            reviewer_id="supervisor-agent",
        )
    )

    assert review_result["success"] is True
    review_data = review_result["data"]

    # Task should now be done after approval
    assert review_data["task"]["id"] == task.id
    assert review_data["task"]["previous_status"] == "pending_completion_review"
    assert review_data["task"]["status"] == "done", (
        f"Approved task should be done, got: {review_data['task']['status']}"
    )

    # Milestone progress should be reported
    assert review_data["milestone_progress"] is not None
    mp = review_data["milestone_progress"]
    assert mp["completed"] >= 1
    assert mp["total"] >= 1
    assert 0 <= mp["pct"] <= 100

    # ------------------------------------------------------------------
    # Verify: task is done and events are recorded
    # ------------------------------------------------------------------
    task.refresh_from_db()
    assert task.status == "done"

    # Review event should be recorded
    review_events = TaskEvent.objects.filter(task=task, event_type="review_submitted")
    assert review_events.exists(), "review_submitted event should be recorded after vtf_review_task"

    # Status change event (pending_completion_review -> done) should be recorded
    status_done_events = TaskEvent.objects.filter(
        task=task, event_type="status_changed", data__to="done"
    )
    assert status_done_events.exists(), "status_changed event (->done) should be recorded"


@pytest.mark.django_db
def test_supervisor_manage_lifecycle():
    """Supervisor creates, submits, blocks, and unblocks a task."""
    # Setup: project with milestone
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)
    milestone = MilestoneFactory(workplan=workplan)

    # ------------------------------------------------------------------
    # Step 1: vtf_manage_task(action="create") — create a new draft task
    # ------------------------------------------------------------------
    create_result = json.loads(
        vtf_manage_task(
            action="create",
            title="Supervisor-managed task",
            project_id=project.id,
            description="A task created by the supervisor workflow",
            milestone_id=milestone.id,
        )
    )

    assert create_result["success"] is True
    create_data = create_result["data"]
    assert "task" in create_data
    task_id = create_data["task"]["id"]
    assert create_data["task"]["status"] == "draft"
    assert task_id, "Created task should have an ID"

    # Draft creation should be recorded as a status event
    from tasks.models import Task
    task_obj = Task.objects.get(pk=task_id)
    assert task_obj.status == "draft"

    # ------------------------------------------------------------------
    # Step 2: vtf_manage_task(action="submit") — submit the task to todo
    # ------------------------------------------------------------------
    submit_result = json.loads(
        vtf_manage_task(action="submit", task_id=task_id)
    )

    assert submit_result["success"] is True
    submit_data = submit_result["data"]
    assert submit_data["task"]["status"] == "todo"
    assert submit_data["task"]["previous_status"] == "draft"

    # Submit event should be recorded
    submitted_events = TaskEvent.objects.filter(
        task=task_obj, event_type="status_changed", data__to="todo"
    )
    assert submitted_events.exists(), "status_changed event (draft->todo) should be recorded"

    # ------------------------------------------------------------------
    # Step 3: vtf_manage_task(action="block") — block the task with reason
    # ------------------------------------------------------------------
    block_reason = "Waiting for upstream API to be deployed"
    block_result = json.loads(
        vtf_manage_task(
            action="block",
            task_id=task_id,
            reason=block_reason,
        )
    )

    assert block_result["success"] is True
    block_data = block_result["data"]
    assert block_data["task"]["status"] == "blocked"
    assert block_data["task"]["previous_status"] == "todo"

    # Block event and reason event should be recorded
    blocked_events = TaskEvent.objects.filter(
        task=task_obj, event_type="status_changed", data__to="blocked"
    )
    assert blocked_events.exists(), "status_changed event (todo->blocked) should be recorded"

    blocked_reason_events = TaskEvent.objects.filter(
        task=task_obj, event_type="blocked_reason"
    )
    assert blocked_reason_events.exists(), "blocked_reason event should be recorded"
    assert blocked_reason_events.first().data.get("reason") == block_reason

    # ------------------------------------------------------------------
    # Step 4: vtf_manage_task(action="unblock") — unblock the task
    # ------------------------------------------------------------------
    unblock_result = json.loads(
        vtf_manage_task(action="unblock", task_id=task_id)
    )

    assert unblock_result["success"] is True
    unblock_data = unblock_result["data"]
    assert unblock_data["task"]["status"] == "todo", (
        f"Unblocked task should be todo, got: {unblock_data['task']['status']}"
    )
    assert unblock_data["task"]["previous_status"] == "blocked"

    # Unblock event should be recorded
    unblocked_events = TaskEvent.objects.filter(
        task=task_obj, event_type="status_changed", data__to="todo"
    )
    # There should be at least 2 todo events: draft->todo and blocked->todo
    assert unblocked_events.count() >= 2, (
        f"Expected at least 2 status_changed->todo events, "
        f"got: {unblocked_events.count()}"
    )

    # ------------------------------------------------------------------
    # Overall lifecycle verification
    # ------------------------------------------------------------------
    task_obj.refresh_from_db()
    assert task_obj.status == "todo"

    # Verify all lifecycle events are in the audit log
    all_events = TaskEvent.objects.filter(task=task_obj)
    assert all_events.count() >= 4, (
        f"Expected at least 4 events (draft->todo, todo->blocked, "
        f"blocked_reason, blocked->todo), got: {all_events.count()}"
    )
