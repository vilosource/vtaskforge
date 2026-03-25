"""
Tests for the vtf_next_work MCP tool (P2.1).

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.workflow import vtf_next_work
from tests.factories import LinkFactory, ProjectFactory, TaskFactory


# ---------------------------------------------------------------------------
# test_next_work_returns_best_candidate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_work_returns_best_candidate():
    """vtf_next_work returns the first claimable task as the candidate."""
    project = ProjectFactory()
    task = TaskFactory(project=project, status="todo")

    result = json.loads(vtf_next_work(project_id=project.id))

    assert result["success"] is True
    assert result["data"] is not None
    assert result["data"]["task"]["id"] == task.id


# ---------------------------------------------------------------------------
# test_next_work_matches_agent_tags
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_work_matches_agent_tags():
    """vtf_next_work filters out tasks whose requirements the agent cannot meet."""
    project = ProjectFactory()
    # Task requires "python" — agent with "docker" only cannot claim it
    requires_python = TaskFactory(project=project, status="todo", requires=["python"])
    # Task with no requirements — any agent can claim it
    no_requirements = TaskFactory(project=project, status="todo", requires=[])

    result = json.loads(vtf_next_work(project_id=project.id, tags="docker"))

    assert result["success"] is True
    assert result["data"] is not None
    # Should not suggest the task requiring python
    assert result["data"]["task"]["id"] != requires_python.id
    assert result["data"]["task"]["id"] == no_requirements.id


# ---------------------------------------------------------------------------
# test_next_work_resolves_dependencies
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_work_resolves_dependencies():
    """vtf_next_work skips tasks with unresolved dependencies."""
    project = ProjectFactory()
    # A blocker task that is not done
    blocker = TaskFactory(project=project, status="todo")
    # A task that depends on the blocker
    blocked_task = TaskFactory(project=project, status="todo")
    LinkFactory(
        source_type="task",
        source_id=blocked_task.id,
        target_type="task",
        target_id=blocker.id,
        link_type="depends_on",
    )
    # A task with no dependencies
    free_task = TaskFactory(project=project, status="todo")

    result = json.loads(vtf_next_work(project_id=project.id))

    assert result["success"] is True
    assert result["data"] is not None
    # Should not suggest the task with unresolved dependency
    assert result["data"]["task"]["id"] != blocked_task.id


# ---------------------------------------------------------------------------
# test_next_work_includes_spec_summary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_work_includes_spec_summary():
    """vtf_next_work includes spec_summary in the response data."""
    project = ProjectFactory()
    task = TaskFactory(
        project=project,
        status="todo",
        spec="description: Implement the feature\nfiles:\n  create:\n    - src/feature.py",
    )

    result = json.loads(vtf_next_work(project_id=project.id))

    assert result["success"] is True
    assert result["data"] is not None
    assert "spec_summary" in result["data"]
    # spec_summary should be from the task's spec field
    assert result["data"]["spec_summary"] == task.spec


# ---------------------------------------------------------------------------
# test_next_work_includes_alternatives_count
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_work_includes_alternatives_count():
    """vtf_next_work includes alternatives count for remaining claimable tasks."""
    project = ProjectFactory()
    # Create 3 claimable tasks; alternatives should be 2 (the other tasks besides the best candidate)
    TaskFactory(project=project, status="todo")
    TaskFactory(project=project, status="todo")
    TaskFactory(project=project, status="todo")

    result = json.loads(vtf_next_work(project_id=project.id))

    assert result["success"] is True
    assert result["data"] is not None
    alternatives = result["data"]["alternatives"]
    assert "count" in alternatives
    assert alternatives["count"] == 2


# ---------------------------------------------------------------------------
# test_next_work_no_work_available
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_work_no_work_available():
    """vtf_next_work returns null data with a helpful message when no tasks are available."""
    project = ProjectFactory()
    # Only done tasks — nothing claimable
    TaskFactory(project=project, status="done")
    TaskFactory(project=project, status="doing")

    result = json.loads(vtf_next_work(project_id=project.id))

    assert result["success"] is True
    assert result["data"] is None
    assert result["message"] != ""
    assert "available_actions" in result
    assert len(result["available_actions"]) > 0


# ---------------------------------------------------------------------------
# test_next_work_with_project_filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_next_work_with_project_filter():
    """vtf_next_work filtered by project_id returns only tasks from that project."""
    project_a = ProjectFactory()
    project_b = ProjectFactory()

    task_a = TaskFactory(project=project_a, status="todo")
    TaskFactory(project=project_b, status="todo")

    result = json.loads(vtf_next_work(project_id=project_a.id))

    assert result["success"] is True
    assert result["data"] is not None
    assert result["data"]["task"]["id"] == task_a.id
