"""
Tests for the vtf_next_work MCP tool (P2.1), vtf_claim_and_start MCP tool (P2.2),
vtf_report_progress MCP tool (P2.3), and vtf_submit_work MCP tool (P2.4).

Tests call the tool Python functions directly (not via MCP protocol).
"""
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from mcp_server.tools._workflow_agent import vtf_claim_and_start, vtf_next_work, vtf_report_progress, vtf_submit_work
from tests.factories import AgentFactory, LinkFactory, MilestoneFactory, ProjectFactory, TaskFactory


@pytest.fixture
def agent1(db):
    """An Agent for claiming tasks in workflow tests."""
    return AgentFactory(name="workflow-agent", tags=[])


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
    requires_python = TaskFactory(project=project, status="todo", required_tags=["python"])
    # Task with no requirements — any agent can claim it
    no_requirements = TaskFactory(project=project, status="todo", required_tags=[])

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
def test_claim_and_start_success(agent1):
    """vtf_claim_and_start claims the task and returns a success response."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

    assert result["success"] is True
    assert result["data"] is not None
    assert result["data"]["task"]["id"] == task.id
    # Task should now be in doing status after claiming
    assert result["data"]["task"]["status"] == "doing"
    assert result["data"]["task"]["claimed_by"] == agent1.user.username


# ---------------------------------------------------------------------------
# test_claim_and_start_includes_spec
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_includes_spec(agent1):
    """vtf_claim_and_start includes the full spec in the response."""
    spec_text = "description: My task spec\nfiles:\n  create:\n    - src/foo.py"
    task = TaskFactory(status="todo", spec=spec_text)

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

    assert result["success"] is True
    assert "spec" in result["data"]
    assert result["data"]["spec"] == spec_text


# ---------------------------------------------------------------------------
# test_claim_and_start_includes_deps
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_includes_deps(agent1):
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

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

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
def test_claim_and_start_includes_test_command(agent1):
    """vtf_claim_and_start includes test_command from the task."""
    test_cmd = {"unit": "pytest tests/foo/ -v", "integration": "pytest tests/integration/"}
    task = TaskFactory(status="todo", test_command=test_cmd)

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

    assert result["success"] is True
    assert "test_command" in result["data"]
    assert result["data"]["test_command"] == test_cmd


# ---------------------------------------------------------------------------
# test_claim_and_start_includes_available_actions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_claim_and_start_includes_available_actions(agent1):
    """vtf_claim_and_start response includes available_actions for next steps."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

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
def test_claim_and_start_tag_mismatch_error(agent1):
    """vtf_claim_and_start returns actionable error when agent tags don't match task requirements."""
    task = TaskFactory(status="todo", required_tags=["python", "docker"])

    # Agent only has "python" — missing "docker"
    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id, tags="python"))

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
def test_claim_and_start_deps_unmet_error(agent1):
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

    result = json.loads(vtf_claim_and_start(task_id=task.id, agent_id=agent1.id))

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


# ===========================================================================
# vtf_report_progress tests (P2.3)
# ===========================================================================


# ---------------------------------------------------------------------------
# test_report_progress_extends_claim
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_report_progress_extends_claim():
    """vtf_report_progress extends claim_expires_at on a doing task."""
    agent = AgentFactory(name="progress-agent")
    old_expires = timezone.now() + timedelta(minutes=5)
    task = TaskFactory(
        status="doing",
        claimed_by=agent.user,
        claimed_at=timezone.now() - timedelta(minutes=25),
        claim_expires_at=old_expires,
    )

    result = json.loads(vtf_report_progress(task_id=task.id))

    assert result["success"] is True
    # claim_expires_at should be extended beyond the old expiry
    task.refresh_from_db()
    assert task.claim_expires_at > old_expires
    # Response data must include the updated claim_expires_at
    assert "claim_expires_at" in result["data"]
    assert result["data"]["task_id"] == task.id


# ---------------------------------------------------------------------------
# test_report_progress_adds_note
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_report_progress_adds_note():
    """vtf_report_progress creates an event via record_event() when a note is provided."""
    from events.models import TaskEvent

    agent = AgentFactory(name="note-agent")
    task = TaskFactory(
        status="doing",
        claimed_by=agent.user,
        claimed_at=timezone.now() - timedelta(minutes=5),
        claim_expires_at=timezone.now() + timedelta(minutes=25),
    )

    result = json.loads(vtf_report_progress(task_id=task.id, note="Halfway done"))

    assert result["success"] is True
    assert result["data"]["note_added"] is True
    # An event should have been created for the note
    events = TaskEvent.objects.filter(task=task, event_type="progress_note")
    assert events.exists()
    assert events.first().data.get("note") == "Halfway done"


# ---------------------------------------------------------------------------
# test_report_progress_without_note
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_report_progress_without_note():
    """vtf_report_progress with no note extends claim but does NOT create an event."""
    from events.models import TaskEvent

    agent = AgentFactory(name="no-note-agent")
    task = TaskFactory(
        status="doing",
        claimed_by=agent.user,
        claimed_at=timezone.now() - timedelta(minutes=5),
        claim_expires_at=timezone.now() + timedelta(minutes=25),
    )

    result = json.loads(vtf_report_progress(task_id=task.id))

    assert result["success"] is True
    assert result["data"]["note_added"] is False
    # No progress_note event should have been created
    events = TaskEvent.objects.filter(task=task, event_type="progress_note")
    assert not events.exists()


# ---------------------------------------------------------------------------
# test_report_progress_not_doing_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_report_progress_not_doing_error():
    """vtf_report_progress returns an error when task is not in 'doing' status."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_report_progress(task_id=task.id))

    assert result["success"] is False
    assert result["message"] != ""
    assert "doing" in result["message"].lower()
    assert "available_actions" in result
    assert len(result["available_actions"]) > 0


# ===========================================================================
# vtf_submit_work tests (P2.4)
# ===========================================================================


# ---------------------------------------------------------------------------
# test_submit_work_completes_task
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submit_work_completes_task():
    """vtf_submit_work moves a doing task with no review flag directly to done."""
    task = TaskFactory(status="doing", needs_review_on_completion=False)

    result = json.loads(vtf_submit_work(task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "done"
    assert result["data"]["task"]["status"] == "done"
    assert result["data"]["review_required"] is False


# ---------------------------------------------------------------------------
# test_submit_work_triggers_review_when_configured
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submit_work_triggers_review_when_configured():
    """vtf_submit_work routes task to pending_completion_review when review flag is set."""
    task = TaskFactory(status="doing", needs_review_on_completion=True)

    result = json.loads(vtf_submit_work(task_id=task.id))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.status == "pending_completion_review"
    assert result["data"]["task"]["status"] == "pending_completion_review"
    assert result["data"]["review_required"] is True


# ---------------------------------------------------------------------------
# test_submit_work_adds_completion_note
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submit_work_adds_completion_note():
    """vtf_submit_work creates a completion_note event when a note is provided."""
    from events.models import TaskEvent

    task = TaskFactory(status="doing", needs_review_on_completion=False)

    result = json.loads(vtf_submit_work(task_id=task.id, completion_note="All tests pass, branch committed."))

    assert result["success"] is True
    events = TaskEvent.objects.filter(task=task, event_type="completion_note")
    assert events.exists()
    assert events.first().data.get("note") == "All tests pass, branch committed."


# ---------------------------------------------------------------------------
# test_submit_work_includes_milestone_progress
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submit_work_includes_milestone_progress():
    """vtf_submit_work response includes milestone_progress with completion counts."""
    milestone = MilestoneFactory()
    # 2 done tasks + 1 we are about to submit = 3 total in milestone
    TaskFactory(milestone=milestone, workplan=milestone.workplan, project=milestone.workplan.project, status="done")
    TaskFactory(milestone=milestone, workplan=milestone.workplan, project=milestone.workplan.project, status="done")
    task = TaskFactory(
        milestone=milestone,
        workplan=milestone.workplan,
        project=milestone.workplan.project,
        status="doing",
        needs_review_on_completion=False,
    )

    result = json.loads(vtf_submit_work(task_id=task.id))

    assert result["success"] is True
    assert "milestone_progress" in result["data"]
    progress = result["data"]["milestone_progress"]
    assert "id" in progress
    assert "title" in progress
    assert "completed" in progress
    assert "total" in progress
    assert "pct" in progress
    # 3 tasks in milestone — all now done
    assert progress["total"] == 3
    assert progress["completed"] == 3


# ---------------------------------------------------------------------------
# test_submit_work_not_doing_error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submit_work_not_doing_error():
    """vtf_submit_work returns an error when task is not in 'doing' status."""
    task = TaskFactory(status="todo")

    result = json.loads(vtf_submit_work(task_id=task.id))

    assert result["success"] is False
    assert result["message"] != ""
    assert "doing" in result["message"].lower()
    assert "available_actions" in result
    assert len(result["available_actions"]) > 0
