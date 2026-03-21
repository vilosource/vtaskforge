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


def test_task_claim_help(runner):
    result = runner.invoke(cli, ["task", "claim", "--help"])
    assert result.exit_code == 0
    assert "--agent" in result.output
    assert "--tags" in result.output
