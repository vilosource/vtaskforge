"""
Tests for the vtf_manage_task MCP tool (P3.3).

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.manage import vtf_manage_task
from tasks.models import Task
from tests.factories import ProjectFactory, TaskFactory


# ---------------------------------------------------------------------------
# test_manage_create_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_create_task():
    """vtf_manage_task(action=create) creates a new task in draft status."""
    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="New feature task",
        project_id=project.id,
    ))

    assert result["success"] is True
    assert result["data"] is not None
    task_data = result["data"]["task"]
    assert task_data["title"] == "New feature task"
    assert task_data["status"] == "draft"
    assert "id" in task_data


# ---------------------------------------------------------------------------
# test_manage_update_title
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_update_title():
    """vtf_manage_task(action=update) updates mutable task fields."""
    task = TaskFactory(status="draft", title="Old title")

    result = json.loads(vtf_manage_task(
        action="update",
        task_id=task.id,
        title="New title",
        description="Updated description",
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.title == "New title"
    assert task.description == "Updated description"


# ---------------------------------------------------------------------------
# test_manage_submit_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_submit_task():
    """vtf_manage_task(action=submit) transitions task from draft to todo."""
    task = TaskFactory(status="draft")

    result = json.loads(vtf_manage_task(action="submit", task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "todo"
    assert result["data"]["task"]["status"] == "todo"


@pytest.mark.django_db
def test_manage_submit_routes_to_pending_start_review_when_flag_set():
    """vtf_manage_task(action=submit) routes to pending_start_review when flag is set."""
    task = TaskFactory(status="draft", needs_review_before_start=True)

    result = json.loads(vtf_manage_task(action="submit", task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "pending_start_review"


@pytest.mark.django_db
def test_manage_submit_routes_to_todo_when_flag_not_set():
    """vtf_manage_task(action=submit) routes to todo when no start review flag."""
    task = TaskFactory(status="draft", needs_review_before_start=False)

    result = json.loads(vtf_manage_task(action="submit", task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "todo"


# ---------------------------------------------------------------------------
# test_manage_block_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_block_task():
    """vtf_manage_task(action=block) transitions task to blocked status."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_manage_task(
        action="block",
        task_id=task.id,
        reason="Waiting for upstream dependency",
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "blocked"
    previous_status = result["data"]["task"]["previous_status"]
    assert previous_status == "todo"


# ---------------------------------------------------------------------------
# test_manage_unblock_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_unblock_task():
    """vtf_manage_task(action=unblock) transitions task from blocked to todo."""
    task = TaskFactory(status="blocked")

    result = json.loads(vtf_manage_task(action="unblock", task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "todo"


# ---------------------------------------------------------------------------
# test_manage_defer_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_defer_task():
    """vtf_manage_task(action=defer) transitions task to deferred status."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_manage_task(action="defer", task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "deferred"


# ---------------------------------------------------------------------------
# test_manage_cancel_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_cancel_task():
    """vtf_manage_task(action=cancel) transitions task to cancelled status."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_manage_task(action="cancel", task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "cancelled"


# ---------------------------------------------------------------------------
# test_manage_delete_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_delete_task():
    """vtf_manage_task(action=delete) deletes the task from the database."""
    from tasks.models import Task

    task = TaskFactory(status="draft")
    task_id = task.id

    result = json.loads(vtf_manage_task(action="delete", task_id=task_id))

    assert result["success"] is True
    assert not Task.objects.filter(pk=task_id).exists()


# ---------------------------------------------------------------------------
# test_manage_assign_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_assign_task():
    """vtf_manage_task(action=assign) sets assigned_to on the task."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_manage_task(
        action="assign",
        task_id=task.id,
        assigned_to="agent-xyz",
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.assigned_to == "agent-xyz"


# ---------------------------------------------------------------------------
# test_manage_invalid_transition_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_invalid_transition_error():
    """vtf_manage_task returns error with valid_transitions when transition is invalid."""
    # done is terminal — cannot block a done task
    task = TaskFactory(status="done")

    result = json.loads(vtf_manage_task(action="block", task_id=task.id))

    assert result["success"] is False
    assert result["message"] != ""
    assert "valid_transitions" in result["data"]
    # done has no valid transitions
    assert result["data"]["valid_transitions"] == []
    assert result["data"]["current_status"] == "done"


# ---------------------------------------------------------------------------
# test_manage_unknown_action_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_unknown_action_error():
    """vtf_manage_task returns error for unknown action values."""
    task = TaskFactory(status="draft")

    result = json.loads(vtf_manage_task(action="frobnicate", task_id=task.id))

    assert result["success"] is False
    assert result["message"] != ""
    assert "frobnicate" in result["message"] or "unknown" in result["message"].lower()


# ---------------------------------------------------------------------------
# test_manage_create_missing_title_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_create_missing_title_error():
    """vtf_manage_task(action=create) returns error when title is missing."""
    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        project_id=project.id,
        # no title
    ))

    assert result["success"] is False
    assert result["message"] != ""
    assert "title" in result["message"].lower()


# ---------------------------------------------------------------------------
# Fuzzy action suggestion tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_fuzzy_cancelled_suggests_cancel():
    """vtf_manage_task(action='cancelled') suggests 'cancel'."""
    result = json.loads(vtf_manage_task(action="cancelled", task_id="fake-id"))

    assert result["success"] is False
    assert "Did you mean 'cancel'?" in result["message"]


@pytest.mark.django_db
def test_manage_fuzzy_submitted_suggests_submit():
    """vtf_manage_task(action='submitted') suggests 'submit'."""
    result = json.loads(vtf_manage_task(action="submitted", task_id="fake-id"))

    assert result["success"] is False
    assert "Did you mean 'submit'?" in result["message"]


@pytest.mark.django_db
def test_manage_fuzzy_blocked_suggests_block():
    """vtf_manage_task(action='blocked') suggests 'block'."""
    result = json.loads(vtf_manage_task(action="blocked", task_id="fake-id"))

    assert result["success"] is False
    assert "Did you mean 'block'?" in result["message"]


@pytest.mark.django_db
def test_manage_fuzzy_blocking_suggests_block():
    """vtf_manage_task(action='blocking') suggests 'block' via -ing stripping."""
    result = json.loads(vtf_manage_task(action="blocking", task_id="fake-id"))

    assert result["success"] is False
    assert "Did you mean 'block'?" in result["message"]


@pytest.mark.django_db
def test_manage_fuzzy_assigns_suggests_assign():
    """vtf_manage_task(action='assigns') suggests 'assign' via -s stripping."""
    result = json.loads(vtf_manage_task(action="assigns", task_id="fake-id"))

    assert result["success"] is False
    assert "Did you mean 'assign'?" in result["message"]


@pytest.mark.django_db
def test_manage_fuzzy_frobnicate_no_suggestion():
    """vtf_manage_task(action='frobnicate') does NOT suggest anything."""
    result = json.loads(vtf_manage_task(action="frobnicate", task_id="fake-id"))

    assert result["success"] is False
    assert "Did you mean" not in result["message"]


# ---------------------------------------------------------------------------
# test_create_task_with_workplan_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_task_with_workplan_id():
    """vtf_manage_task(action=create, workplan_id=WP_ID) creates task with workplan set."""
    from tests.factories import WorkplanFactory

    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)

    result = json.loads(vtf_manage_task(
        action="create",
        title="Task in workplan",
        project_id=project.id,
        workplan_id=workplan.id,
    ))

    assert result["success"] is True
    task_data = result["data"]["task"]
    assert task_data["status"] == "draft"

    from tasks.models import Task
    task = Task.objects.get(pk=task_data["id"])
    assert task.workplan_id == workplan.id
    assert task.milestone is None


# ---------------------------------------------------------------------------
# test_create_task_with_workplan_and_milestone
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_task_with_workplan_and_milestone():
    """When both workplan_id and milestone_id are provided on create, milestone wins."""
    from tests.factories import MilestoneFactory, WorkplanFactory

    project = ProjectFactory()
    workplan_a = WorkplanFactory(project=project)
    workplan_b = WorkplanFactory(project=project)
    milestone = MilestoneFactory(workplan=workplan_b)

    result = json.loads(vtf_manage_task(
        action="create",
        title="Task with both",
        project_id=project.id,
        workplan_id=workplan_a.id,
        milestone_id=milestone.id,
    ))

    assert result["success"] is True
    task_data = result["data"]["task"]

    from tasks.models import Task
    task = Task.objects.get(pk=task_data["id"])
    # milestone_id takes precedence — workplan should be milestone's workplan
    assert task.milestone_id == milestone.id
    assert task.workplan_id == workplan_b.id


# ---------------------------------------------------------------------------
# test_update_task_workplan_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_task_workplan_id():
    """vtf_manage_task(action=update, workplan_id=WP_ID) moves task to new workplan."""
    from tests.factories import WorkplanFactory

    task = TaskFactory(status="draft")
    new_workplan = WorkplanFactory(project=task.project)

    result = json.loads(vtf_manage_task(
        action="update",
        task_id=task.id,
        workplan_id=new_workplan.id,
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.workplan_id == new_workplan.id


# ---------------------------------------------------------------------------
# test_update_task_workplan_clears_mismatched_milestone
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_task_workplan_clears_mismatched_milestone():
    """Moving task to new workplan clears a milestone that belongs to the old workplan."""
    from tests.factories import MilestoneFactory, WorkplanFactory

    project = ProjectFactory()
    workplan_a = WorkplanFactory(project=project)
    workplan_b = WorkplanFactory(project=project)
    milestone_a = MilestoneFactory(workplan=workplan_a)

    task = TaskFactory(
        status="draft",
        project=project,
        workplan=workplan_a,
        milestone=milestone_a,
    )

    result = json.loads(vtf_manage_task(
        action="update",
        task_id=task.id,
        workplan_id=workplan_b.id,
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.workplan_id == workplan_b.id
    assert task.milestone is None


# ---------------------------------------------------------------------------
# test_create_task_invalid_workplan_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_task_invalid_workplan_id():
    """vtf_manage_task(action=create) with invalid workplan_id returns error."""
    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="Task with bad workplan",
        project_id=project.id,
        workplan_id="nonexistent-workplan-id",
    ))

    assert result["success"] is False
    assert "nonexistent-workplan-id" in result["message"] or "not found" in result["message"].lower()


# ---------------------------------------------------------------------------
# test_create_with_acceptance_criteria_json
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_with_acceptance_criteria_json():
    """vtf_manage_task(action=create) accepts acceptance_criteria as JSON array."""
    from tasks.models import Task

    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="AC JSON test",
        project_id=project.id,
        acceptance_criteria='["AC1: must pass", "AC2: must be fast"]',
    ))

    assert result["success"] is True
    task = Task.objects.get(pk=result["data"]["task"]["id"])
    assert task.acceptance_criteria == ["AC1: must pass", "AC2: must be fast"]


# ---------------------------------------------------------------------------
# test_create_with_acceptance_criteria_csv
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_with_acceptance_criteria_csv():
    """vtf_manage_task(action=create) accepts acceptance_criteria as comma-separated string."""
    from tasks.models import Task

    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="AC CSV test",
        project_id=project.id,
        acceptance_criteria="AC1: must pass, AC2: must be fast",
    ))

    assert result["success"] is True
    task = Task.objects.get(pk=result["data"]["task"]["id"])
    assert task.acceptance_criteria == ["AC1: must pass", "AC2: must be fast"]


# ---------------------------------------------------------------------------
# test_create_with_requires_valid
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_with_requires_valid():
    """vtf_manage_task(action=create) sets requires field with valid task IDs."""
    from tasks.models import Task

    project = ProjectFactory()
    dep1 = TaskFactory(status="draft", project=project)
    dep2 = TaskFactory(status="draft", project=project)

    result = json.loads(vtf_manage_task(
        action="create",
        title="Task with dependencies",
        project_id=project.id,
        requires=f"{dep1.id},{dep2.id}",
    ))

    assert result["success"] is True
    task = Task.objects.get(pk=result["data"]["task"]["id"])
    assert set(task.requires) == {dep1.id, dep2.id}


# ---------------------------------------------------------------------------
# test_create_with_requires_invalid
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_with_requires_invalid():
    """vtf_manage_task(action=create) returns error when required task IDs don't exist."""
    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="Task with bad deps",
        project_id=project.id,
        requires="nonexistent-task-id-1,nonexistent-task-id-2",
    ))

    assert result["success"] is False
    assert "not found" in result["message"].lower()
    assert "missing_ids" in result["data"]


# ---------------------------------------------------------------------------
# test_create_with_review_booleans
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_with_review_booleans():
    """vtf_manage_task(action=create) sets needs_review_* fields from string true/false."""
    from tasks.models import Task

    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="Review flags test",
        project_id=project.id,
        needs_review_before_start="true",
        needs_review_on_completion="false",
    ))

    assert result["success"] is True
    task = Task.objects.get(pk=result["data"]["task"]["id"])
    assert task.needs_review_before_start is True
    assert task.needs_review_on_completion is False


# ---------------------------------------------------------------------------
# test_create_with_test_command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_with_test_command():
    """vtf_manage_task(action=create) sets test_command from valid JSON dict."""
    from tasks.models import Task

    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="Test command test",
        project_id=project.id,
        test_command='{"unit": "pytest tests/mcp_server/", "full": "pytest tests/"}',
    ))

    assert result["success"] is True
    task = Task.objects.get(pk=result["data"]["task"]["id"])
    assert task.test_command == {"unit": "pytest tests/mcp_server/", "full": "pytest tests/"}


# ---------------------------------------------------------------------------
# test_create_with_test_command_invalid_json
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_with_test_command_plain_string_accepted():
    """vtf_manage_task(action=create) accepts plain string test_command (auto-wrapped)."""
    project = ProjectFactory()

    result = json.loads(vtf_manage_task(
        action="create",
        title="Plain test command",
        project_id=project.id,
        test_command="pytest tests/ -v",
    ))

    assert result["success"] is True
    task = Task.objects.get(pk=result["data"]["task"]["id"])
    assert task.test_command == {"command": "pytest tests/ -v"}


# ---------------------------------------------------------------------------
# test_update_acceptance_criteria
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_acceptance_criteria():
    """vtf_manage_task(action=update) modifies acceptance_criteria on existing task."""
    task = TaskFactory(status="draft", acceptance_criteria=["old criterion"])

    result = json.loads(vtf_manage_task(
        action="update",
        task_id=task.id,
        acceptance_criteria='["new criterion A", "new criterion B"]',
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.acceptance_criteria == ["new criterion A", "new criterion B"]


# ---------------------------------------------------------------------------
# test_update_requires
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_requires():
    """vtf_manage_task(action=update) modifies requires field on existing task."""
    task = TaskFactory(status="draft", requires=[])
    dep = TaskFactory(status="draft", project=task.project)

    result = json.loads(vtf_manage_task(
        action="update",
        task_id=task.id,
        requires=dep.id,
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.requires == [dep.id]


# ---------------------------------------------------------------------------
# test_manage_note_on_draft_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_note_on_draft_task():
    """vtf_manage_task(action=note) adds a note event to a task in draft status."""
    from events.models import TaskEvent

    task = TaskFactory(status="draft")

    result = json.loads(vtf_manage_task(
        action="note",
        task_id=task.id,
        reason="This is a note on a draft task",
    ))

    assert result["success"] is True
    assert result["data"]["task"]["id"] == task.id
    assert result["data"]["task"]["status"] == "draft"
    assert TaskEvent.objects.filter(task=task, event_type="note").exists()
    event = TaskEvent.objects.get(task=task, event_type="note")
    assert event.data["text"] == "This is a note on a draft task"


# ---------------------------------------------------------------------------
# test_manage_note_on_todo_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_note_on_todo_task():
    """vtf_manage_task(action=note) adds a note event to a task in todo status."""
    from events.models import TaskEvent

    task = TaskFactory(status="todo")

    result = json.loads(vtf_manage_task(
        action="note",
        task_id=task.id,
        reason="Note on a todo task",
    ))

    assert result["success"] is True
    assert result["data"]["task"]["status"] == "todo"
    assert TaskEvent.objects.filter(task=task, event_type="note").exists()


# ---------------------------------------------------------------------------
# test_manage_note_on_done_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_note_on_done_task():
    """vtf_manage_task(action=note) adds a note event to a task in done status."""
    from events.models import TaskEvent

    task = TaskFactory(status="done")

    result = json.loads(vtf_manage_task(
        action="note",
        task_id=task.id,
        reason="Retrospective note on completed task",
    ))

    assert result["success"] is True
    assert result["data"]["task"]["status"] == "done"
    assert TaskEvent.objects.filter(task=task, event_type="note").exists()


# ---------------------------------------------------------------------------
# test_manage_note_missing_task_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_note_missing_task_id():
    """vtf_manage_task(action=note) returns error when task_id is missing."""
    result = json.loads(vtf_manage_task(
        action="note",
        reason="Some note text",
    ))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()


# ---------------------------------------------------------------------------
# test_manage_note_missing_note_text
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_note_missing_note_text():
    """vtf_manage_task(action=note) returns error when reason (note text) is missing."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_manage_task(
        action="note",
        task_id=task.id,
        # no reason
    ))

    assert result["success"] is False
    assert "reason" in result["message"].lower()


# ---------------------------------------------------------------------------
# recover action tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_mcp_recover_action_to_todo():
    """vtf_manage_task(action=recover) re-queues a needs_attention task to todo."""
    task = TaskFactory(status="needs_attention", retry_count=0)

    result = json.loads(vtf_manage_task(
        action="recover",
        task_id=task.id,
        reason="Retrying after environment fix",
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "todo"
    assert task.retry_count == 1
    assert task.claimed_by is None
    assert task.claimed_at is None
    assert task.claim_expires_at is None
    assert result["data"]["task"]["status"] == "todo"
    assert result["data"]["task"]["retry_count"] == 1


@pytest.mark.django_db
def test_mcp_recover_action_to_draft():
    """vtf_manage_task(action=recover, target=draft) resets task to draft for major rework."""
    task = TaskFactory(status="needs_attention", retry_count=1)

    result = json.loads(vtf_manage_task(
        action="recover",
        task_id=task.id,
        target="draft",
        reason="Major rework needed — spec was wrong",
    ))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "draft"
    assert task.retry_count == 1  # not incremented for draft
    assert task.claimed_by is None
    assert result["data"]["task"]["status"] == "draft"


@pytest.mark.django_db
def test_mcp_recover_requires_reason():
    """vtf_manage_task(action=recover) returns error when reason is missing."""
    task = TaskFactory(status="needs_attention")

    result = json.loads(vtf_manage_task(
        action="recover",
        task_id=task.id,
    ))

    assert result["success"] is False
    assert "reason" in result["message"].lower()


@pytest.mark.django_db
def test_mcp_recover_requires_task_id():
    """vtf_manage_task(action=recover) returns error when task_id is missing."""
    result = json.loads(vtf_manage_task(
        action="recover",
        reason="Retrying",
    ))

    assert result["success"] is False
    assert "task_id" in result["message"].lower()


@pytest.mark.django_db
def test_mcp_recover_invalid_target():
    """vtf_manage_task(action=recover) returns error for unknown target."""
    task = TaskFactory(status="needs_attention")

    result = json.loads(vtf_manage_task(
        action="recover",
        task_id=task.id,
        reason="Retrying",
        target="doing",
    ))

    assert result["success"] is False
    assert "target" in result["message"].lower()


@pytest.mark.django_db
def test_mcp_recover_from_wrong_status():
    """vtf_manage_task(action=recover) returns error when task is not needs_attention."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_manage_task(
        action="recover",
        task_id=task.id,
        reason="Retrying",
    ))

    assert result["success"] is False
    assert "needs_attention" in result["message"]


@pytest.mark.django_db
def test_mcp_recover_increments_retry_count_multiple_times():
    """retry_count accumulates across multiple recover-to-todo calls."""
    task = TaskFactory(status="needs_attention", retry_count=2)

    vtf_manage_task(action="recover", task_id=task.id, reason="attempt 3")
    task.refresh_from_db()
    assert task.retry_count == 3
