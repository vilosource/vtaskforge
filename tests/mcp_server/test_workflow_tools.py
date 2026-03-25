"""
Tests for the vtf_next_work MCP tool (P2.1) and vtf_claim_and_start MCP tool (P2.2).

Tests call the tool Python functions directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.workflow import vtf_claim_and_start, vtf_next_work
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


# ===========================================================================
# vtf_claim_and_start tests (P2.2)
# ===========================================================================


# ---------------------------------------------------------------------------
# test_claim_and_start_success
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_success():
    """vtf_claim_and_start claims the task and returns a success response."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id="agent-1"))

    assert result["success"] is True
    assert result["data"] is not None
    assert result["data"]["task"]["id"] == task.id
    # Task should now be in doing status after claiming
    assert result["data"]["task"]["status"] == "doing"
    assert result["data"]["task"]["claimed_by"] == "agent-1"


# ---------------------------------------------------------------------------
# test_claim_and_start_includes_spec
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_includes_spec():
    """vtf_claim_and_start includes the full spec in the response."""
    spec_text = "description: My task spec\nfiles:\n  create:\n    - src/foo.py"
    task = TaskFactory(status="todo", spec=spec_text)

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id="agent-1"))

    assert result["success"] is True
    assert "spec" in result["data"]
    assert result["data"]["spec"] == spec_text


# ---------------------------------------------------------------------------
# test_claim_and_start_includes_deps
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_includes_deps():
    """vtf_claim_and_start includes dependency status in the response."""
    done_dep = TaskFactory(status="done")
    task = TaskFactory(status="todo")
    LinkFactory(
        source_type="task",
        source_id=task.id,
        target_type="task",
        target_id=done_dep.id,
        link_type="depends_on",
    )

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id="agent-1"))

    assert result["success"] is True
    assert "dependencies" in result["data"]
    deps = result["data"]["dependencies"]
    assert "resolved" in deps
    assert deps["resolved"] is True
    dep_ids = [d["id"] for d in deps["dependencies"]]
    assert done_dep.id in dep_ids


# ---------------------------------------------------------------------------
# test_claim_and_start_includes_test_command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_includes_test_command():
    """vtf_claim_and_start includes test_command from the task."""
    test_cmd = {"unit": "pytest tests/foo/ -v", "integration": "pytest tests/integration/"}
    task = TaskFactory(status="todo", test_command=test_cmd)

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id="agent-1"))

    assert result["success"] is True
    assert "test_command" in result["data"]
    assert result["data"]["test_command"] == test_cmd


# ---------------------------------------------------------------------------
# test_claim_and_start_includes_available_actions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_includes_available_actions():
    """vtf_claim_and_start response includes available_actions for next steps."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id="agent-1"))

    assert result["success"] is True
    assert "available_actions" in result
    actions = result["available_actions"]
    assert len(actions) > 0
    # After claiming, agent should be able to report progress or submit work
    assert any("report_progress" in a for a in actions)
    assert any("submit_work" in a for a in actions)


# ---------------------------------------------------------------------------
# test_claim_and_start_tag_mismatch_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_tag_mismatch_error():
    """vtf_claim_and_start returns actionable error when agent tags don't match task requirements."""
    task = TaskFactory(status="todo", requires=["python", "docker"])

    # Agent only has "python" — missing "docker"
    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id="agent-1", tags="python"))

    assert result["success"] is False
    assert result["message"] != ""
    # Message should be actionable — explain what went wrong
    assert "tag" in result["message"].lower() or "require" in result["message"].lower()
    # Error response must include available_actions
    assert "available_actions" in result
    assert len(result["available_actions"]) > 0
    # Should suggest finding other work
    assert any("next_work" in a for a in result["available_actions"])


# ---------------------------------------------------------------------------
# test_claim_and_start_deps_unmet_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_deps_unmet_error():
    """vtf_claim_and_start returns actionable error with which dep is blocking when deps are unmet."""
    blocker = TaskFactory(status="doing")
    task = TaskFactory(status="todo")
    LinkFactory(
        source_type="task",
        source_id=task.id,
        target_type="task",
        target_id=blocker.id,
        link_type="depends_on",
    )

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id="agent-1"))

    assert result["success"] is False
    assert result["message"] != ""
    # Message should reference the blocking dependency
    assert blocker.id in result["message"]
    # data should contain unresolved dep info
    assert "data" in result
    assert result["data"] is not None
    # available_actions should guide agent to next steps
    assert "available_actions" in result
    assert len(result["available_actions"]) > 0
