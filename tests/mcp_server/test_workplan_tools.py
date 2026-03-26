"""
Tests for the vtf_manage_workplan MCP tool.

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.workplan import vtf_manage_workplan
from tests.factories import ProjectFactory, WorkplanFactory, MilestoneFactory, TaskFactory


# ---------------------------------------------------------------------------
# test_manage_workplan_create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_workplan_create():
    """vtf_manage_workplan(action=create) creates a new workplan with name and project."""
    project = ProjectFactory()

    result = json.loads(vtf_manage_workplan(
        action="create",
        name="Sprint Alpha",
        project_id=project.id,
    ))

    assert result["success"] is True
    wp_data = result["data"]["workplan"]
    assert wp_data["name"] == "Sprint Alpha"
    assert wp_data["status"] == "active"
    assert "id" in wp_data


@pytest.mark.django_db
def test_manage_workplan_create_missing_name():
    """vtf_manage_workplan(action=create) returns error when name is missing."""
    project = ProjectFactory()

    result = json.loads(vtf_manage_workplan(
        action="create",
        project_id=project.id,
        # no name
    ))

    assert result["success"] is False
    assert "name" in result["message"].lower()


@pytest.mark.django_db
def test_manage_workplan_create_missing_project_id():
    """vtf_manage_workplan(action=create) returns error when project_id is missing."""
    result = json.loads(vtf_manage_workplan(
        action="create",
        name="Orphan Workplan",
        # no project_id
    ))

    assert result["success"] is False
    assert "project_id" in result["message"].lower() or "project" in result["message"].lower()


@pytest.mark.django_db
def test_manage_workplan_create_invalid_project_id():
    """vtf_manage_workplan(action=create) returns error when project does not exist."""
    result = json.loads(vtf_manage_workplan(
        action="create",
        name="Bad Project Workplan",
        project_id="nonexistent-project-id",
    ))

    assert result["success"] is False
    assert "nonexistent-project-id" in result["message"] or "not found" in result["message"].lower()


# ---------------------------------------------------------------------------
# test_manage_workplan_list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_workplan_list():
    """vtf_manage_workplan(action=list) returns workplans with milestone and task counts."""
    project = ProjectFactory()
    wp = WorkplanFactory(project=project)
    milestone = MilestoneFactory(workplan=wp)
    TaskFactory(workplan=wp, milestone=milestone, status="todo")
    TaskFactory(workplan=wp, milestone=milestone, status="done")

    result = json.loads(vtf_manage_workplan(action="list"))

    assert result["success"] is True
    workplans = result["data"]["workplans"]
    assert isinstance(workplans, list)

    # Find the workplan we created
    wp_data = next((w for w in workplans if w["id"] == wp.id), None)
    assert wp_data is not None
    assert wp_data["name"] == wp.name
    assert wp_data["status"] == "active"
    assert "milestone_count" in wp_data
    assert wp_data["milestone_count"] == 1
    assert "task_counts" in wp_data
    assert wp_data["task_counts"]["todo"] == 1
    assert wp_data["task_counts"]["done"] == 1


@pytest.mark.django_db
def test_manage_workplan_list_project_filter():
    """vtf_manage_workplan(action=list) with project_id filter returns only that project's workplans."""
    project_a = ProjectFactory()
    project_b = ProjectFactory()
    wp_a = WorkplanFactory(project=project_a, name="WP Alpha")
    wp_b = WorkplanFactory(project=project_b, name="WP Beta")

    result = json.loads(vtf_manage_workplan(action="list", project_id=project_a.id))

    assert result["success"] is True
    workplans = result["data"]["workplans"]
    ids = [w["id"] for w in workplans]
    assert wp_a.id in ids
    assert wp_b.id not in ids


@pytest.mark.django_db
def test_manage_workplan_list_status_filter():
    """vtf_manage_workplan(action=list) with status filter returns only matching workplans."""
    project = ProjectFactory()
    wp_active = WorkplanFactory(project=project, status="active")
    wp_archived = WorkplanFactory(project=project, status="archived")

    result = json.loads(vtf_manage_workplan(action="list", status="active"))

    assert result["success"] is True
    workplans = result["data"]["workplans"]
    ids = [w["id"] for w in workplans]
    assert wp_active.id in ids
    assert wp_archived.id not in ids


# ---------------------------------------------------------------------------
# test_manage_workplan_update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_workplan_update():
    """vtf_manage_workplan(action=update) modifies name, description, and tags."""
    wp = WorkplanFactory(name="Old Name", description="Old desc", tags=[])

    result = json.loads(vtf_manage_workplan(
        action="update",
        workplan_id=wp.id,
        name="New Name",
        description="New description",
        tags="alpha,beta,gamma",
    ))

    assert result["success"] is True
    wp.refresh_from_db()
    assert wp.name == "New Name"
    assert wp.description == "New description"
    assert wp.tags == ["alpha", "beta", "gamma"]


@pytest.mark.django_db
def test_manage_workplan_update_missing_workplan_id():
    """vtf_manage_workplan(action=update) returns error when workplan_id is missing."""
    result = json.loads(vtf_manage_workplan(
        action="update",
        name="New Name",
        # no workplan_id
    ))

    assert result["success"] is False
    assert "workplan_id" in result["message"].lower() or "workplan" in result["message"].lower()


@pytest.mark.django_db
def test_manage_workplan_update_invalid_workplan_id():
    """vtf_manage_workplan(action=update) returns error when workplan does not exist."""
    result = json.loads(vtf_manage_workplan(
        action="update",
        workplan_id="nonexistent-workplan-id",
        name="New Name",
    ))

    assert result["success"] is False
    assert "nonexistent-workplan-id" in result["message"] or "not found" in result["message"].lower()


# ---------------------------------------------------------------------------
# test_manage_workplan_archive
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_workplan_archive():
    """vtf_manage_workplan(action=archive) sets workplan status to archived."""
    wp = WorkplanFactory(status="active")

    result = json.loads(vtf_manage_workplan(
        action="archive",
        workplan_id=wp.id,
    ))

    assert result["success"] is True
    wp.refresh_from_db()
    assert wp.status == "archived"


@pytest.mark.django_db
def test_manage_workplan_archive_missing_workplan_id():
    """vtf_manage_workplan(action=archive) returns error when workplan_id is missing."""
    result = json.loads(vtf_manage_workplan(action="archive"))

    assert result["success"] is False
    assert "workplan_id" in result["message"].lower() or "workplan" in result["message"].lower()


# ---------------------------------------------------------------------------
# test_manage_workplan_complete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_workplan_complete():
    """vtf_manage_workplan(action=complete) sets workplan status to completed."""
    wp = WorkplanFactory(status="active")

    result = json.loads(vtf_manage_workplan(
        action="complete",
        workplan_id=wp.id,
    ))

    assert result["success"] is True
    wp.refresh_from_db()
    assert wp.status == "completed"


@pytest.mark.django_db
def test_manage_workplan_complete_missing_workplan_id():
    """vtf_manage_workplan(action=complete) returns error when workplan_id is missing."""
    result = json.loads(vtf_manage_workplan(action="complete"))

    assert result["success"] is False
    assert "workplan_id" in result["message"].lower() or "workplan" in result["message"].lower()


# ---------------------------------------------------------------------------
# test_manage_workplan_unknown_action
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_manage_workplan_unknown_action():
    """vtf_manage_workplan returns error for unknown action values."""
    result = json.loads(vtf_manage_workplan(action="frobnicate"))

    assert result["success"] is False
    assert "frobnicate" in result["message"] or "unknown" in result["message"].lower()
