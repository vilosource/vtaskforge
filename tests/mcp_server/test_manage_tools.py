"""
Tests for the vtf_manage_task MCP tool (P3.3).

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.manage import vtf_manage_task
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
