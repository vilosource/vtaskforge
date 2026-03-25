"""
Tests for the vtf_search_tasks MCP tool (P3.1).

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.search import vtf_search_tasks
from tests.factories import MilestoneFactory, ProjectFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# test_search_by_status
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_by_status():
    """Filtering by status returns only tasks with that status."""
    project = ProjectFactory()
    todo_task = TaskFactory(project=project, status="todo")
    TaskFactory(project=project, status="doing")
    TaskFactory(project=project, status="done")

    result = json.loads(vtf_search_tasks(status="todo"))

    assert result["success"] is True
    task_ids = [t["id"] for t in result["data"]["tasks"]]
    assert todo_task.id in task_ids
    for t in result["data"]["tasks"]:
        assert t["status"] == "todo"


# ---------------------------------------------------------------------------
# test_search_by_project
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_by_project():
    """Filtering by project_id returns only tasks for that project."""
    project_a = ProjectFactory()
    project_b = ProjectFactory()
    task_a = TaskFactory(project=project_a, status="todo")
    TaskFactory(project=project_b, status="todo")

    result = json.loads(vtf_search_tasks(project_id=project_a.id))

    assert result["success"] is True
    task_ids = [t["id"] for t in result["data"]["tasks"]]
    assert task_a.id in task_ids
    for t in result["data"]["tasks"]:
        assert t["id"] != TaskFactory.__name__  # all belong to project_a
    # All returned tasks must belong to project_a
    from tasks.models import Task
    for t_dict in result["data"]["tasks"]:
        task = Task.objects.get(pk=t_dict["id"])
        assert task.project_id == project_a.id


# ---------------------------------------------------------------------------
# test_search_by_milestone
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_by_milestone():
    """Filtering by milestone_id returns only tasks in that milestone."""
    workplan = WorkplanFactory()
    milestone_a = MilestoneFactory(workplan=workplan)
    milestone_b = MilestoneFactory(workplan=workplan)
    task_a = TaskFactory(
        milestone=milestone_a,
        workplan=workplan,
        project=workplan.project,
        status="todo",
    )
    TaskFactory(
        milestone=milestone_b,
        workplan=workplan,
        project=workplan.project,
        status="todo",
    )

    result = json.loads(vtf_search_tasks(milestone_id=milestone_a.id))

    assert result["success"] is True
    task_ids = [t["id"] for t in result["data"]["tasks"]]
    assert task_a.id in task_ids
    # All returned tasks belong to milestone_a
    from tasks.models import Task
    for t_dict in result["data"]["tasks"]:
        task = Task.objects.get(pk=t_dict["id"])
        assert task.milestone_id == milestone_a.id


# ---------------------------------------------------------------------------
# test_search_by_labels
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_by_labels():
    """Filtering by labels returns only tasks containing all specified labels."""
    project = ProjectFactory()
    task_with_label = TaskFactory(project=project, labels=["backend", "security"])
    TaskFactory(project=project, labels=["frontend"])
    TaskFactory(project=project, labels=[])

    result = json.loads(vtf_search_tasks(labels="backend"))

    assert result["success"] is True
    task_ids = [t["id"] for t in result["data"]["tasks"]]
    assert task_with_label.id in task_ids
    # No task without 'backend' label should appear
    from tasks.models import Task
    for t_dict in result["data"]["tasks"]:
        task = Task.objects.get(pk=t_dict["id"])
        assert "backend" in task.labels


# ---------------------------------------------------------------------------
# test_search_text_query
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_text_query():
    """Text query filters by title and description."""
    project = ProjectFactory()
    task_match_title = TaskFactory(
        project=project, title="Add rate limiting middleware", description="some desc"
    )
    task_match_desc = TaskFactory(
        project=project, title="Unrelated title", description="Implements rate limiter"
    )
    TaskFactory(project=project, title="Completely different", description="No match here")

    result = json.loads(vtf_search_tasks(query="rate limit"))

    assert result["success"] is True
    task_ids = [t["id"] for t in result["data"]["tasks"]]
    assert task_match_title.id in task_ids
    assert task_match_desc.id in task_ids


# ---------------------------------------------------------------------------
# test_search_pagination
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_pagination():
    """Pagination returns correct slice and metadata."""
    project = ProjectFactory()
    for _ in range(5):
        TaskFactory(project=project)

    # Fetch first 2
    result_page1 = json.loads(vtf_search_tasks(project_id=project.id, limit=2, offset=0))
    assert result_page1["success"] is True
    data1 = result_page1["data"]
    assert len(data1["tasks"]) == 2
    assert data1["total_count"] == 5
    assert data1["has_more"] is True
    assert data1["offset"] == 0
    assert data1["limit"] == 2

    # Fetch next 2
    result_page2 = json.loads(vtf_search_tasks(project_id=project.id, limit=2, offset=2))
    data2 = result_page2["data"]
    assert len(data2["tasks"]) == 2
    assert data2["offset"] == 2
    assert data2["has_more"] is True

    # Fetch last page
    result_page3 = json.loads(vtf_search_tasks(project_id=project.id, limit=2, offset=4))
    data3 = result_page3["data"]
    assert len(data3["tasks"]) == 1
    assert data3["has_more"] is False


# ---------------------------------------------------------------------------
# test_search_includes_available_actions_per_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_includes_available_actions_per_task():
    """Each task in search results includes available_actions list."""
    project = ProjectFactory()
    TaskFactory(project=project, status="todo")
    TaskFactory(project=project, status="done")

    result = json.loads(vtf_search_tasks(project_id=project.id))

    assert result["success"] is True
    for task in result["data"]["tasks"]:
        assert "available_actions" in task
        assert isinstance(task["available_actions"], list)
