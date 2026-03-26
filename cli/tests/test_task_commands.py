import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf.client import VTFAPIError


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


# --- list ---

def test_task_list_success(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "status": "doing"},
        {"id": "task-002", "title": "Write tests", "status": "todo"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 0
    assert "task-001" in result.output
    assert "Build API" in result.output
    assert "doing" in result.output
    assert "task-002" in result.output
    assert "Write tests" in result.output
    assert "ID" in result.output
    assert "Title" in result.output
    assert "Status" in result.output


def test_task_list_empty(runner, mock_client):
    mock_client.get.return_value = []
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 0
    assert "No tasks found" in result.output


def test_task_list_with_status_filter(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "status": "doing"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list", "--status", "doing"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/v1/tasks/", params={"status": "doing"})


def test_task_list_with_workplan_filter(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "status": "todo"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/v1/tasks/", params={"workplan": "wp-abc"})


def test_task_list_with_milestone_filter(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "status": "todo"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list", "--milestone", "ms-123"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/v1/tasks/", params={"milestone": "ms-123"})


def test_task_list_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(500, {"error": {"message": "Server error"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 1


def test_task_list_long_title_truncated(runner, mock_client):
    long_title = "A" * 40
    mock_client.get.return_value = [
        {"id": "task-001", "title": long_title, "status": "todo"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list"])
    assert result.exit_code == 0
    assert ".." in result.output


# --- show ---

def test_task_show_success(runner, mock_client):
    mock_client.get.return_value = {
        "id": "task-abc",
        "title": "Implement auth",
        "status": "doing",
        "milestone": "ms-1",
        "workplan": "wp-1",
        "claimed_by": "agent-x",
        "requires": ["task-000"],
        "description": "Full auth implementation",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "show", "task-abc"])
    assert result.exit_code == 0
    assert "task-abc" in result.output
    assert "Implement auth" in result.output
    assert "doing" in result.output
    assert "ms-1" in result.output
    assert "wp-1" in result.output
    assert "agent-x" in result.output
    assert "task-000" in result.output
    assert "Full auth implementation" in result.output
    mock_client.get.assert_called_once_with("/v1/tasks/task-abc/")


def test_task_show_no_description(runner, mock_client):
    mock_client.get.return_value = {
        "id": "task-min",
        "title": "Minimal task",
        "status": "todo",
        "milestone": "",
        "workplan": "",
        "claimed_by": None,
        "requires": [],
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "show", "task-min"])
    assert result.exit_code == 0
    assert "task-min" in result.output
    assert "None" in result.output or "none" in result.output


def test_task_show_not_found(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "show", "nonexistent"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- submit ---

def test_task_submit_success(runner, mock_client):
    mock_client.post.return_value = {"status": "submitted"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "submit", "task-abc"])
    assert result.exit_code == 0
    assert "Submitted task task-abc" in result.output
    assert "submitted" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/submit/")


def test_task_submit_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Invalid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "submit", "task-abc"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- claim ---

def test_task_claim_success(runner, mock_client):
    mock_client.post.return_value = {"status": "claimed"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claim", "task-abc", "--agent", "agent-1"])
    assert result.exit_code == 0
    assert "Claimed task task-abc by agent-1" in result.output
    assert "claimed" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/claim/", {"agent_id": "agent-1"})


def test_task_claim_with_tags(runner, mock_client):
    mock_client.post.return_value = {"status": "claimed"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "claim", "task-abc", "--agent", "agent-1", "--tags", "python,docker"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["agent_id"] == "agent-1"
    assert call_data["tags"] == ["python", "docker"]


def test_task_claim_missing_agent(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claim", "task-abc"])
    assert result.exit_code != 0


def test_task_claim_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(409, {"error": {"message": "Already claimed"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claim", "task-abc", "--agent", "agent-1"])
    assert result.exit_code == 1


# --- complete ---

def test_task_complete_success(runner, mock_client):
    mock_client.post.return_value = {"status": "done"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "complete", "task-abc"])
    assert result.exit_code == 0
    assert "Completed task task-abc" in result.output
    assert "done" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/complete/")


def test_task_complete_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Not in valid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "complete", "task-abc"])
    assert result.exit_code == 1


# --- fail ---

def test_task_fail_success(runner, mock_client):
    mock_client.post.return_value = {"status": "failed"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "fail", "task-abc"])
    assert result.exit_code == 0
    assert "Failed task task-abc" in result.output
    assert "failed" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/fail/")


def test_task_fail_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Not in valid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "fail", "task-abc"])
    assert result.exit_code == 1


# --- claimable ---

def test_task_claimable_success(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "requires": ["python"]},
        {"id": "task-002", "title": "Write tests", "requires": []},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claimable"])
    assert result.exit_code == 0
    assert "task-001" in result.output
    assert "Build API" in result.output
    assert "task-002" in result.output
    assert "ID" in result.output
    assert "Title" in result.output
    assert "Requires" in result.output
    mock_client.get.assert_called_once_with("/v1/tasks/claimable/", params=None)


def test_task_claimable_with_tags(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "requires": ["python"]},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claimable", "--tags", "python,docker"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with(
        "/v1/tasks/claimable/", params={"tags": "python,docker"}
    )


def test_task_claimable_empty(runner, mock_client):
    mock_client.get.return_value = []
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claimable"])
    assert result.exit_code == 0
    assert "No claimable tasks" in result.output


def test_task_claimable_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(500, {"error": {"message": "Server error"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claimable"])
    assert result.exit_code == 1


def test_task_list_with_project_filter(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "status": "todo"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "list", "--project", "proj-123"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/v1/tasks/", params={"project": "proj-123"})


def test_task_claimable_with_project_filter(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "task-001", "title": "Build API", "requires": []},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "claimable", "--project", "proj-123"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/v1/tasks/claimable/", params={"project": "proj-123"})


# --- create ---

def test_task_create_success(runner, mock_client):
    mock_client.post.return_value = {
        "id": "task-123",
        "title": "Test Task",
        "status": "draft",
        "project": "proj-abc",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "create", "Test Task", "--project", "proj-abc"])
    assert result.exit_code == 0
    assert "Created task task-123" in result.output
    assert "Test Task" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/tasks/", {"title": "Test Task", "description": "", "project": "proj-abc"}
    )


def test_task_create_with_labels(runner, mock_client):
    mock_client.post.return_value = {
        "id": "task-456",
        "title": "Labeled Task",
        "status": "draft",
        "project": "proj-abc",
        "labels": ["bugfix", "ui"],
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "create", "Labeled Task", "--project", "proj-abc", "--labels", "bugfix,ui"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["labels"] == ["bugfix", "ui"]


def test_task_create_with_workplan_and_milestone(runner, mock_client):
    mock_client.post.return_value = {
        "id": "task-789",
        "title": "Structured Task",
        "status": "draft",
        "project": "proj-abc",
        "workplan": "wp-123",
        "milestone": "ms-456",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "create", "Structured Task", "--project", "proj-abc", "--workplan", "wp-123", "--milestone", "ms-456"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["workplan"] == "wp-123"
    assert call_data["milestone"] == "ms-456"


def test_task_create_missing_project(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "create", "Test Task"])
    assert result.exit_code == 1
    assert "project is required" in result.output


def test_task_create_with_default_project(runner, mock_client):
    mock_client.post.return_value = {
        "id": "task-999",
        "title": "Default Project Task",
        "status": "draft",
        "project": "proj-default",
    }
    with patch("vtf.cli.get_client", return_value=mock_client), \
         patch("vtf.commands.task.Config") as mock_config_cls:
        mock_config = mock_config_cls.return_value
        mock_config.project = "proj-default"
        result = runner.invoke(cli, ["task", "create", "Default Project Task"])
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["project"] == "proj-default"


def test_task_create_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Invalid data"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "create", "Fail Task", "--project", "proj-abc"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- events ---

def test_task_events_success(runner, mock_client):
    mock_client.get.return_value = {
        "results": [
            {"event_type": "created", "triggered_by": "agent-1", "data": {"note": "init"}},
            {"event_type": "status_changed", "triggered_by": "system", "data": {"from": "todo", "to": "doing"}},
        ]
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "events", "task-abc"])
    assert result.exit_code == 0
    assert "created" in result.output
    assert "agent-1" in result.output
    assert "status_changed" in result.output
    mock_client.get.assert_called_once_with("/v1/tasks/task-abc/events/")


def test_task_events_paginated_list(runner, mock_client):
    mock_client.get.return_value = [
        {"event_type": "created", "triggered_by": "agent-1", "data": {}},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "events", "task-abc"])
    assert result.exit_code == 0
    assert "created" in result.output


def test_task_events_empty(runner, mock_client):
    mock_client.get.return_value = {"results": []}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "events", "task-abc"])
    assert result.exit_code == 0
    assert "No events found" in result.output


def test_task_events_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "events", "nonexistent"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- help ---

def test_task_help(runner):
    result = runner.invoke(cli, ["task", "--help"])
    assert result.exit_code == 0
    assert "task" in result.output.lower()


def test_task_list_help(runner):
    result = runner.invoke(cli, ["task", "list", "--help"])
    assert result.exit_code == 0
    assert "--status" in result.output
    assert "--workplan" in result.output
    assert "--milestone" in result.output
    assert "--project" in result.output


def test_task_claim_help(runner):
    result = runner.invoke(cli, ["task", "claim", "--help"])
    assert result.exit_code == 0
    assert "--agent" in result.output
    assert "--tags" in result.output


# --- reset ---

def test_task_reset_success(runner, mock_client):
    mock_client.post.return_value = {"status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "reset", "task-abc", "--status", "draft", "--reason", "board recovery"],
        )
    assert result.exit_code == 0
    assert "Reset task task-abc" in result.output
    assert "draft" in result.output
    assert "board recovery" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/tasks/task-abc/reset/",
        {"status": "draft", "reason": "board recovery"},
    )


def test_task_reset_missing_status(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "reset", "task-abc", "--reason", "test"],
        )
    assert result.exit_code != 0


def test_task_reset_missing_reason(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "reset", "task-abc", "--status", "draft"],
        )
    assert result.exit_code != 0


def test_task_reset_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Invalid status"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "reset", "task-abc", "--status", "invalid", "--reason", "test"],
        )
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- approve ---

def test_task_approve_success(runner, mock_client):
    mock_client.post.return_value = {"decision": "approved"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "approve", "task-abc"])
    assert result.exit_code == 0
    assert "Approved task task-abc" in result.output
    assert "approved" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/tasks/task-abc/reviews/",
        {"decision": "approved", "reason": "", "reviewer_id": "cli-user", "reviewer_type": "human"},
    )


def test_task_approve_with_reason(runner, mock_client):
    mock_client.post.return_value = {"decision": "approved"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "approve", "task-abc", "--reason", "looks good"])
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["reason"] == "looks good"


def test_task_approve_api_error_404(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "approve", "nonexistent"])
    assert result.exit_code == 1


def test_task_approve_api_error_invalid_state(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Task not in review state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "approve", "task-abc"])
    assert result.exit_code == 1


# --- reject ---

def test_task_reject_success(runner, mock_client):
    mock_client.post.return_value = {"decision": "changes_requested"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "reject", "task-abc", "--reason", "needs rework"])
    assert result.exit_code == 0
    assert "Rejected task task-abc" in result.output
    assert "changes_requested" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/tasks/task-abc/reviews/",
        {"decision": "changes_requested", "reason": "needs rework", "reviewer_id": "cli-user", "reviewer_type": "human"},
    )


def test_task_reject_missing_reason(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "reject", "task-abc"])
    assert result.exit_code != 0


def test_task_reject_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Invalid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "reject", "task-abc", "--reason", "bad"])
    assert result.exit_code == 1


# --- review ---

def test_task_review_approved(runner, mock_client):
    mock_client.post.return_value = {"decision": "approved"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "approved"],
        )
    assert result.exit_code == 0
    assert "Review submitted for task task-abc" in result.output
    assert "decision=approved" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/tasks/task-abc/reviews/",
        {"decision": "approved", "reason": "", "reviewer_id": "cli-user", "reviewer_type": "human"},
    )


def test_task_review_changes_requested_with_reason(runner, mock_client):
    mock_client.post.return_value = {"decision": "changes_requested"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "changes_requested", "--reason", "Fix tests"],
        )
    assert result.exit_code == 0
    assert "Review submitted" in result.output
    assert "changes_requested" in result.output
    call_data = mock_client.post.call_args[0][1]
    assert call_data["reason"] == "Fix tests"


def test_task_review_changes_requested_missing_reason(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "changes_requested"],
        )
    assert result.exit_code == 1
    assert "reason is required" in result.output.lower() or "--reason" in result.output


def test_task_review_rejected_missing_reason(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "rejected"],
        )
    assert result.exit_code == 1


def test_task_review_missing_decision(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc"],
        )
    assert result.exit_code != 0


def test_task_review_invalid_decision(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "invalid"],
        )
    assert result.exit_code != 0


def test_task_review_api_error_404(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "approved"],
        )
    assert result.exit_code == 1


def test_task_review_api_error_invalid_state(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Not in review state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "approved"],
        )
    assert result.exit_code == 1


def test_task_review_custom_reviewer(runner, mock_client):
    mock_client.post.return_value = {"decision": "approved"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["task", "review", "task-abc", "--decision", "approved", "--reviewer", "judge-agent", "--reviewer-type", "agent"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["reviewer_id"] == "judge-agent"
    assert call_data["reviewer_type"] == "agent"


# --- block ---

def test_task_block_success(runner, mock_client):
    mock_client.post.return_value = {"status": "blocked"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "block", "task-abc"])
    assert result.exit_code == 0
    assert "Blocked task task-abc" in result.output
    assert "blocked" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/block/", None)


def test_task_block_with_reason(runner, mock_client):
    mock_client.post.return_value = {"status": "blocked"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "block", "task-abc", "--reason", "waiting on API"])
    assert result.exit_code == 0
    mock_client.post.assert_called_once_with(
        "/v1/tasks/task-abc/block/", {"reason": "waiting on API"}
    )


def test_task_block_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Invalid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "block", "task-abc"])
    assert result.exit_code == 1


# --- unblock ---

def test_task_unblock_success(runner, mock_client):
    mock_client.post.return_value = {"status": "todo"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "unblock", "task-abc"])
    assert result.exit_code == 0
    assert "Unblocked task task-abc" in result.output
    assert "todo" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/unblock/")


def test_task_unblock_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Invalid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "unblock", "task-abc"])
    assert result.exit_code == 1


# --- defer ---

def test_task_defer_success(runner, mock_client):
    mock_client.post.return_value = {"status": "deferred"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "defer", "task-abc"])
    assert result.exit_code == 0
    assert "Deferred task task-abc" in result.output
    assert "deferred" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/defer/")


def test_task_defer_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Invalid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "defer", "task-abc"])
    assert result.exit_code == 1


# --- cancel ---

def test_task_cancel_success(runner, mock_client):
    mock_client.post.return_value = {"status": "cancelled"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "cancel", "task-abc"])
    assert result.exit_code == 0
    assert "Cancelled task task-abc" in result.output
    assert "cancelled" in result.output
    mock_client.post.assert_called_once_with("/v1/tasks/task-abc/cancel/")


def test_task_cancel_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Invalid state"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "cancel", "task-abc"])
    assert result.exit_code == 1


# --- delete ---

def test_task_delete_with_yes_flag(runner, mock_client):
    mock_client.delete.return_value = {}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "delete", "task-abc", "--yes"])
    assert result.exit_code == 0
    assert "Deleted task task-abc" in result.output
    mock_client.delete.assert_called_once_with("/v1/tasks/task-abc/")


def test_task_delete_confirm_yes(runner, mock_client):
    mock_client.delete.return_value = {}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "delete", "task-abc"], input="y\n")
    assert result.exit_code == 0
    assert "Deleted task task-abc" in result.output
    mock_client.delete.assert_called_once_with("/v1/tasks/task-abc/")


def test_task_delete_confirm_no(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "delete", "task-abc"], input="n\n")
    assert result.exit_code == 1
    mock_client.delete.assert_not_called()


def test_task_delete_api_error(runner, mock_client):
    mock_client.delete.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "delete", "task-abc", "--yes"])
    assert result.exit_code == 1


# --- update ---

def test_task_update_title(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "title": "New title", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--title", "New title"])
    assert result.exit_code == 0
    assert "Updated task task-abc" in result.output
    mock_client.patch.assert_called_once_with("/v1/tasks/task-abc/", {"title": "New title"})


def test_task_update_multiple_fields(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--title", "X", "--description", "Y"]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"title": "X", "description": "Y"}
    )


def test_task_update_labels(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--labels", "bug,ui"])
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"labels": ["bug", "ui"]}
    )


def test_task_update_spec_inline(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--spec", "do the thing"])
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"spec": "do the thing"}
    )


def test_task_update_spec_file(runner, mock_client, tmp_path):
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text("description: test spec\n")
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--spec-file", str(spec_file)]
        )
    assert result.exit_code == 0
    call_data = mock_client.patch.call_args[0][1]
    assert call_data["spec"] == "description: test spec\n"


def test_task_update_judge_flag(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--judge"])
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with("/v1/tasks/task-abc/", {"judge": True})


def test_task_update_no_judge_flag(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--no-judge"])
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with("/v1/tasks/task-abc/", {"judge": False})


def test_task_update_no_options(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc"])
    assert result.exit_code == 1
    assert "no fields to update" in result.output.lower()


def test_task_update_api_error(runner, mock_client):
    mock_client.patch.side_effect = VTFAPIError(400, {"error": {"message": "Invalid data"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--title", "X"])
    assert result.exit_code == 1


def test_task_update_workplan(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--workplan", "wp-123"])
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with("/v1/tasks/task-abc/", {"workplan": "wp-123"})


def test_task_update_milestone(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["task", "update", "task-abc", "--milestone", "ms-456"])
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with("/v1/tasks/task-abc/", {"milestone": "ms-456"})


def test_task_update_acceptance_criteria(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    criteria = '["AC1: does X", "AC2: does Y"]'
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--acceptance-criteria", criteria]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"acceptance_criteria": ["AC1: does X", "AC2: does Y"]}
    )


def test_task_update_requires(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--requires", "task-1,task-2"]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"requires": ["task-1", "task-2"]}
    )


def test_task_update_test_command(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    test_cmd = '{"unit": "pytest tests/", "full": "pytest"}'
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--test-command", test_cmd]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/",
        {"test_command": {"unit": "pytest tests/", "full": "pytest"}},
    )


def test_task_update_needs_review_before_start(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--needs-review-before-start"]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"needs_review_before_start": True}
    )


def test_task_update_no_review_before_start(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--no-review-before-start"]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"needs_review_before_start": False}
    )


def test_task_update_needs_review_on_completion(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--needs-review-on-completion"]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"needs_review_on_completion": True}
    )


def test_task_update_no_review_on_completion(runner, mock_client):
    mock_client.patch.return_value = {"id": "task-abc", "status": "draft"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--no-review-on-completion"]
        )
    assert result.exit_code == 0
    mock_client.patch.assert_called_once_with(
        "/v1/tasks/task-abc/", {"needs_review_on_completion": False}
    )


def test_task_update_acceptance_criteria_invalid_json(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--acceptance-criteria", "not-json"]
        )
    assert result.exit_code == 1
    assert "invalid json" in result.output.lower()


def test_task_update_test_command_invalid_json(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli, ["task", "update", "task-abc", "--test-command", "not-json"]
        )
    assert result.exit_code == 1
    assert "invalid json" in result.output.lower()


def test_task_update_help_shows_new_flags(runner):
    result = runner.invoke(cli, ["task", "update", "--help"])
    assert result.exit_code == 0
    assert "--workplan" in result.output
    assert "--milestone" in result.output
    assert "--acceptance-criteria" in result.output
    assert "--requires" in result.output
    assert "--test-command" in result.output
    assert "--needs-review-before-start" in result.output
    assert "--needs-review-on-completion" in result.output
