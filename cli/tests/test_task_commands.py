import json
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError
from vtf_sdk.refs import ProjectRef, WorkplanRef, MilestoneRef, TaskRef
from tests.sdk_mock_helpers import make_task, make_paged


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


# --- list ---

def test_task_list_success(runner, mock_client):
    mock_client.tasks.list.return_value = make_paged([
        make_task(id="task-001", title="Build API", status="doing"),
        make_task(id="task-002", title="Write tests", status="todo"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 0
    assert "task-001" in result.output
    assert "Build API" in result.output
    assert "doing" in result.output
    assert "task-002" in result.output


def test_task_list_empty(runner, mock_client):
    mock_client.tasks.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 0
    assert "No tasks found" in result.output


def test_task_list_with_status_filter(runner, mock_client):
    mock_client.tasks.list.return_value = make_paged([make_task(status="doing")])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list", "--status", "doing"])
    assert result.exit_code == 0
    mock_client.tasks.list.assert_called_once()
    call_kwargs = mock_client.tasks.list.call_args[1]
    assert call_kwargs["status"] == "doing"


def test_task_list_with_workplan_filter(runner, mock_client):
    mock_client.tasks.list.return_value = make_paged([make_task()])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    call_kwargs = mock_client.tasks.list.call_args[1]
    assert call_kwargs["workplan_id"] == "wp-abc"


def test_task_list_with_milestone_filter(runner, mock_client):
    mock_client.tasks.list.return_value = make_paged([make_task()])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list", "--milestone", "ms-123"])
    assert result.exit_code == 0
    call_kwargs = mock_client.tasks.list.call_args[1]
    assert call_kwargs["milestone_id"] == "ms-123"


def test_task_list_api_error(runner, mock_client):
    mock_client.tasks.list.side_effect = VtfError("UNKNOWN", "Server error")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 1


def test_task_list_long_title_truncated(runner, mock_client):
    mock_client.tasks.list.return_value = make_paged([make_task(title="A" * 40)])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 0
    assert ".." in result.output


# --- show ---

def test_task_show_success(runner, mock_client):
    mock_client.tasks.get.return_value = make_task(
        id="task-abc", title="Implement auth", status="doing",
        milestone=MilestoneRef(id="ms-1", name="Phase 1", status="active"),
        workplan=WorkplanRef(id="wp-1", name="Sprint 1"),
        description="Full auth implementation",
        requires=[TaskRef(id="task-000", title="Setup", status="done")],
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "show", "task-abc"])
    assert result.exit_code == 0
    assert "task-abc" in result.output
    assert "Implement auth" in result.output
    assert "doing" in result.output
    assert "Full auth implementation" in result.output


def test_task_show_no_description(runner, mock_client):
    mock_client.tasks.get.return_value = make_task(id="task-min", title="Minimal task")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "show", "task-min"])
    assert result.exit_code == 0
    assert "task-min" in result.output


def test_task_show_not_found(runner, mock_client):
    from vtf_sdk.exceptions import NotFound
    mock_client.tasks.get.side_effect = NotFound("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "show", "nonexistent"])
    assert result.exit_code == 1


def test_task_show_json(runner, mock_client):
    mock_client.tasks.get.return_value = make_task(id="task-json", title="JSON Test")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "show", "task-json", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == "task-json"


# --- submit ---

def test_task_submit_success(runner, mock_client):
    mock_client.tasks.submit.return_value = make_task(status="todo")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "submit", "task-abc"])
    assert result.exit_code == 0
    assert "Submitted task task-abc" in result.output
    assert "todo" in result.output


def test_task_submit_api_error(runner, mock_client):
    mock_client.tasks.submit.side_effect = VtfError("INVALID_TRANSITION", "Invalid state")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "submit", "task-abc"])
    assert result.exit_code == 1


# --- claim ---

def test_task_claim_success(runner, mock_client):
    mock_client.tasks.claim.return_value = make_task(status="doing")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claim", "task-abc", "--agent", "agent-1"])
    assert result.exit_code == 0
    assert "Claimed task task-abc by agent-1" in result.output


def test_task_claim_missing_agent(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claim", "task-abc"])
    assert result.exit_code != 0


def test_task_claim_api_error(runner, mock_client):
    mock_client.tasks.claim.side_effect = VtfError("ALREADY_CLAIMED", "Already claimed")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claim", "task-abc", "--agent", "agent-1"])
    assert result.exit_code == 1


# --- complete ---

def test_task_complete_success(runner, mock_client):
    mock_client.tasks.complete.return_value = make_task(status="done")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "complete", "task-abc"])
    assert result.exit_code == 0
    assert "Completed task task-abc" in result.output
    assert "done" in result.output


def test_task_complete_api_error(runner, mock_client):
    mock_client.tasks.complete.side_effect = VtfError("INVALID_TRANSITION", "Not in valid state")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "complete", "task-abc"])
    assert result.exit_code == 1


# --- fail ---

def test_task_fail_success(runner, mock_client):
    mock_client.tasks.fail.return_value = make_task(status="needs_attention")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "fail", "task-abc"])
    assert result.exit_code == 0
    assert "Failed task task-abc" in result.output


def test_task_fail_api_error(runner, mock_client):
    mock_client.tasks.fail.side_effect = VtfError("INVALID_TRANSITION", "Not in valid state")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "fail", "task-abc"])
    assert result.exit_code == 1


# --- claimable ---

def test_task_claimable_success(runner, mock_client):
    mock_client.tasks.claimable.return_value = make_paged([
        make_task(id="task-001", title="Build API", requires=[TaskRef(id="dep-1", title="Dep", status="done")]),
        make_task(id="task-002", title="Write tests"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claimable"])
    assert result.exit_code == 0
    assert "task-001" in result.output
    assert "Build API" in result.output


def test_task_claimable_empty(runner, mock_client):
    mock_client.tasks.claimable.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claimable"])
    assert result.exit_code == 0
    assert "No claimable tasks" in result.output


# --- create ---

def test_task_create_success(runner, mock_client):
    mock_client.tasks.create.return_value = make_task(id="task-new", title="New Task")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "create", "New Task", "--project", "p1"])
    assert result.exit_code == 0
    assert "Created task task-new" in result.output


def test_task_create_missing_project(runner, mock_client, monkeypatch):
    monkeypatch.delenv("VTF_PROJECT", raising=False)
    with patch("vtf.cli.get_client", return_value=mock_client), \
         patch("vtf.commands.task.Config") as MockConfig:
        MockConfig.return_value.project = None
        result = runner.invoke(cli, ["task", "create", "No Project"])
    assert result.exit_code == 1
    assert "project is required" in result.output


def test_task_create_api_error(runner, mock_client):
    mock_client.tasks.create.side_effect = VtfError("VALIDATION_ERROR", "Invalid")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "create", "Fail", "--project", "p1"])
    assert result.exit_code == 1


def test_task_create_required_tags(runner, mock_client):
    mock_client.tasks.create.return_value = make_task(id="task-new", title="New Task")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, [
            "task", "create", "New Task", "--project", "p1",
            "--required-tags", "executor,pi",
        ])
    assert result.exit_code == 0
    _, kwargs = mock_client.tasks.create.call_args
    assert kwargs.get("required_tags") == ["executor", "pi"]


# --- review ---

def test_task_review_success(runner, mock_client):
    from vtf_sdk.entities import Review
    from vtf_sdk.refs import TaskRef, UserActor
    mock_client.tasks.submit_review.return_value = Review(
        id="rev-1", task=TaskRef(id="t1", title="T", status="doing"),
        decision="approved", reason="LGTM",
        reviewer=UserActor(type="user", id="1", username="cli-user"),
        reviewer_type="human",
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "review", "task-abc", "--decision", "approved"])
    assert result.exit_code == 0
    assert "approved" in result.output


def test_task_review_reject_requires_reason(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "review", "task-abc", "--decision", "changes_requested"])
    assert result.exit_code == 1
    assert "reason is required" in result.output.lower()


# --- reset ---

def test_task_reset_success(runner, mock_client):
    mock_client.tasks.reset.return_value = make_task(status="todo")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "reset", "task-abc", "--status", "todo", "--reason", "test"])
    assert result.exit_code == 0
    assert "Reset task task-abc" in result.output


# --- approve/reject shortcuts ---

def test_task_approve_success(runner, mock_client):
    from vtf_sdk.entities import Review
    from vtf_sdk.refs import TaskRef, UserActor
    mock_client.tasks.submit_review.return_value = Review(
        id="rev-1", task=TaskRef(id="t1", title="T", status="doing"),
        decision="approved", reason="",
        reviewer=UserActor(type="user", id="1", username="cli-user"),
        reviewer_type="human",
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "approve", "task-abc"])
    assert result.exit_code == 0
    assert "Approved task task-abc" in result.output


def test_task_reject_success(runner, mock_client):
    from vtf_sdk.entities import Review
    from vtf_sdk.refs import TaskRef, UserActor
    mock_client.tasks.submit_review.return_value = Review(
        id="rev-1", task=TaskRef(id="t1", title="T", status="doing"),
        decision="changes_requested", reason="Needs work",
        reviewer=UserActor(type="user", id="1", username="cli-user"),
        reviewer_type="human",
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "reject", "task-abc", "--reason", "Needs work"])
    assert result.exit_code == 0
    assert "Rejected task task-abc" in result.output


# --- block/unblock/defer/cancel ---

def test_task_block_success(runner, mock_client):
    mock_client.tasks.block.return_value = make_task(status="blocked")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "block", "task-abc"])
    assert result.exit_code == 0
    assert "Blocked task task-abc" in result.output


def test_task_unblock_success(runner, mock_client):
    mock_client.tasks.unblock.return_value = make_task(status="todo")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "unblock", "task-abc"])
    assert result.exit_code == 0
    assert "Unblocked task task-abc" in result.output


def test_task_defer_success(runner, mock_client):
    mock_client.tasks.defer.return_value = make_task(status="deferred")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "defer", "task-abc"])
    assert result.exit_code == 0
    assert "Deferred task task-abc" in result.output


def test_task_cancel_success(runner, mock_client):
    mock_client.tasks.cancel.return_value = make_task(status="cancelled")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "cancel", "task-abc"])
    assert result.exit_code == 0
    assert "Cancelled task task-abc" in result.output


# --- delete ---

def test_task_delete_success(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "delete", "task-abc", "--yes"])
    assert result.exit_code == 0
    assert "Deleted task task-abc" in result.output
    mock_client.tasks.delete.assert_called_once_with("task-abc")


def test_task_delete_api_error(runner, mock_client):
    mock_client.tasks.delete.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "delete", "task-abc", "--yes"])
    assert result.exit_code == 1


# --- update ---

def test_task_update_title(runner, mock_client):
    mock_client.tasks.update.return_value = make_task(title="New Title")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--title", "New Title"])
    assert result.exit_code == 0
    assert "Updated task task-abc" in result.output


def test_task_update_no_fields(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc"])
    assert result.exit_code == 1
    assert "no fields" in result.output.lower()


def test_task_update_api_error(runner, mock_client):
    mock_client.tasks.update.side_effect = VtfError("VALIDATION_ERROR", "Invalid")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--title", "Fail"])
    assert result.exit_code == 1


def test_task_update_required_tags(runner, mock_client):
    mock_client.tasks.update.return_value = make_task()
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, [
            "task", "update", "task-abc", "--required-tags", "executor,pi",
        ])
    assert result.exit_code == 0
    args, kwargs = mock_client.tasks.update.call_args
    assert kwargs.get("required_tags") == ["executor", "pi"]


def test_task_update_requires_with_task_ids_wraps_as_taskref(runner, mock_client):
    mock_client.tasks.update.return_value = make_task()
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, [
            "task", "update", "task-abc", "--requires", "tsk-aaa,tsk-bbb",
        ])
    assert result.exit_code == 0
    _, kwargs = mock_client.tasks.update.call_args
    assert kwargs.get("requires") == [{"id": "tsk-aaa"}, {"id": "tsk-bbb"}]


def test_task_update_requires_with_bare_strings_warns_and_routes_to_required_tags(runner, mock_client):
    mock_client.tasks.update.return_value = make_task()
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, [
            "task", "update", "task-abc", "--requires", "executor,pi",
        ])
    assert result.exit_code == 0
    assert "use --required-tags" in result.output.lower()
    _, kwargs = mock_client.tasks.update.call_args
    assert kwargs.get("required_tags") == ["executor", "pi"]
    assert "requires" not in kwargs


# --- events ---

def test_task_events_success(runner, mock_client):
    from vtf_sdk.entities import TaskEvent
    from vtf_sdk.refs import TaskRef
    mock_client.tasks.list_events.return_value = make_paged([
        TaskEvent(id="e1", task=TaskRef(id="t1", title="T", status="doing"),
                  event_type="claimed", data={"agent_id": "a1"},
                  trigger_source="claim"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "events", "task-abc"])
    assert result.exit_code == 0
    assert "claimed" in result.output


def test_task_events_empty(runner, mock_client):
    mock_client.tasks.list_events.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "events", "task-abc"])
    assert result.exit_code == 0
    assert "No events found" in result.output


# --- help ---

def test_task_help(runner):
    result = runner.invoke(cli, ["task", "--help"])
    assert result.exit_code == 0

def test_task_list_help(runner):
    result = runner.invoke(cli, ["task", "list", "--help"])
    assert result.exit_code == 0

def test_task_show_help(runner):
    result = runner.invoke(cli, ["task", "show", "--help"])
    assert result.exit_code == 0

def test_task_create_help(runner):
    result = runner.invoke(cli, ["task", "create", "--help"])
    assert result.exit_code == 0

def test_task_update_help(runner):
    result = runner.invoke(cli, ["task", "update", "--help"])
    assert result.exit_code == 0
