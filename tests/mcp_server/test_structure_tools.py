"""
Tests for the vtf_workplan_tree MCP tool.

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.structure import vtf_workplan_tree
from tests.factories import MilestoneFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# test_workplan_tree_with_milestones_and_tasks
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_workplan_tree_with_milestones_and_tasks():
    """vtf_workplan_tree returns workplan with milestones ordered by order field and tasks."""
    wp = WorkplanFactory(name="Tree Workplan")
    ms1 = MilestoneFactory(workplan=wp, name="Milestone One", status="active", order=1)
    ms2 = MilestoneFactory(workplan=wp, name="Milestone Two", status="pending", order=2)
    t1 = TaskFactory(workplan=wp, milestone=ms1, title="Task Alpha", status="todo", labels=["backend"])
    t2 = TaskFactory(workplan=wp, milestone=ms2, title="Task Beta", status="draft", labels=[])

    result = json.loads(vtf_workplan_tree(workplan_id=wp.id))

    assert result["success"] is True
    data = result["data"]

    # Workplan info
    assert data["workplan"]["id"] == wp.id
    assert data["workplan"]["name"] == "Tree Workplan"
    assert data["workplan"]["status"] == "active"

    # Milestones ordered by order field
    milestones = data["milestones"]
    assert len(milestones) == 2
    assert milestones[0]["id"] == ms1.id
    assert milestones[0]["name"] == "Milestone One"
    assert milestones[0]["status"] == "active"
    assert milestones[0]["order"] == 1
    assert milestones[1]["id"] == ms2.id
    assert milestones[1]["order"] == 2

    # Tasks in first milestone
    tasks_ms1 = milestones[0]["tasks"]
    assert len(tasks_ms1) == 1
    assert tasks_ms1[0]["id"] == t1.id
    assert tasks_ms1[0]["title"] == "Task Alpha"
    assert tasks_ms1[0]["status"] == "todo"
    assert tasks_ms1[0]["labels"] == ["backend"]

    # Tasks in second milestone
    tasks_ms2 = milestones[1]["tasks"]
    assert len(tasks_ms2) == 1
    assert tasks_ms2[0]["id"] == t2.id
    assert tasks_ms2[0]["labels"] == []

    # No unassigned tasks
    assert data["unassigned_tasks"] == []


# ---------------------------------------------------------------------------
# test_workplan_tree_with_unassigned_tasks
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_workplan_tree_with_unassigned_tasks():
    """vtf_workplan_tree shows tasks with workplan but no milestone in unassigned_tasks."""
    wp = WorkplanFactory(name="Unassigned Workplan")
    ms = MilestoneFactory(workplan=wp, name="First Milestone", order=1)
    assigned = TaskFactory(workplan=wp, milestone=ms, title="Assigned Task", status="todo")

    # Task with workplan but no milestone
    from tasks.models import Task

    unassigned = Task.objects.create(
        workplan=wp,
        project=wp.project,
        milestone=None,
        title="Unassigned Task",
        status="draft",
        labels=["orphan"],
    )

    result = json.loads(vtf_workplan_tree(workplan_id=wp.id))

    assert result["success"] is True
    data = result["data"]

    # Milestone has the assigned task
    assert len(data["milestones"]) == 1
    assert len(data["milestones"][0]["tasks"]) == 1
    assert data["milestones"][0]["tasks"][0]["id"] == assigned.id

    # Unassigned task appears in unassigned_tasks
    unassigned_tasks = data["unassigned_tasks"]
    assert len(unassigned_tasks) == 1
    assert unassigned_tasks[0]["id"] == unassigned.id
    assert unassigned_tasks[0]["title"] == "Unassigned Task"
    assert unassigned_tasks[0]["status"] == "draft"
    assert unassigned_tasks[0]["labels"] == ["orphan"]


# ---------------------------------------------------------------------------
# test_workplan_tree_empty_workplan
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_workplan_tree_empty_workplan():
    """vtf_workplan_tree returns empty milestones and unassigned_tasks for workplan with nothing."""
    wp = WorkplanFactory(name="Empty Workplan")

    result = json.loads(vtf_workplan_tree(workplan_id=wp.id))

    assert result["success"] is True
    data = result["data"]
    assert data["workplan"]["id"] == wp.id
    assert data["milestones"] == []
    assert data["unassigned_tasks"] == []


# ---------------------------------------------------------------------------
# test_workplan_tree_invalid_workplan_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_workplan_tree_invalid_workplan_id():
    """vtf_workplan_tree returns error for nonexistent workplan_id."""
    result = json.loads(vtf_workplan_tree(workplan_id="nonexistent-id"))

    assert result["success"] is False
    assert "not found" in result["message"].lower() or "nonexistent-id" in result["message"]
