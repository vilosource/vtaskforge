"""
Tests for the vtf_task_detail MCP tool (P3.2).

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.detail import vtf_task_detail
from tests.factories import ReviewFactory, TaskEventFactory, TaskFactory


# ---------------------------------------------------------------------------
# test_task_detail_includes_all_sections
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_detail_includes_all_sections():
    """vtf_task_detail returns full context: spec, deps, reviews, events, notes, available_actions."""
    task = TaskFactory(
        status="todo",
        spec="description: Test spec",
        acceptance_criteria=["Criterion 1"],
    )
    review = ReviewFactory(task=task, decision="approved", reason="LGTM")
    event = TaskEventFactory(task=task, event_type="status_changed")
    note_event = TaskEventFactory(task=task, event_type="progress_note")

    result = json.loads(vtf_task_detail(task_id=task.id))

    assert result["success"] is True
    data = result["data"]

    # Task fields
    assert data["task"]["id"] == task.id
    assert data["task"]["status"] == "todo"

    # Spec
    assert data["spec"] == "description: Test spec"

    # Acceptance criteria (inside task object in v2 format)
    assert data["task"]["acceptance_criteria"] == ["Criterion 1"]

    # Dependencies section
    assert "dependencies" in data
    assert "resolved" in data["dependencies"]

    # Reviews
    assert "reviews" in data

    # Events (was recent_events)
    assert "events" in data

    # Notes
    assert "notes" in data

    # Available actions
    assert "available_actions" in result


# ---------------------------------------------------------------------------
# test_task_detail_shows_available_actions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_detail_shows_available_actions():
    """vtf_task_detail includes available_actions reflecting valid transitions."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_task_detail(task_id=task.id))

    assert result["success"] is True
    # 'todo' status allows claiming (transition to 'doing')
    assert result["available_actions"] is not None
    assert isinstance(result["available_actions"], list)
    # available_actions should be non-empty for a todo task
    assert len(result["available_actions"]) > 0


# ---------------------------------------------------------------------------
# test_task_detail_not_found_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_detail_not_found_error():
    """vtf_task_detail returns error_response when task does not exist."""
    result = json.loads(vtf_task_detail(task_id="nonexistent-task-id"))

    assert result["success"] is False
    assert "not found" in result["message"].lower()
