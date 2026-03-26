import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf.client import VTFAPIError
from vtf.config import Config
from vtf.commands.workplan import milestone


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def cli_with_mock_client(mock_client):
    """Invoke CLI with a mock client injected via ctx.obj."""
    with patch("vtf.cli.get_client", return_value=mock_client):
        yield mock_client


# --- create ---

def test_workplan_create_success(runner, mock_client):
    mock_client.post.return_value = {
        "id": "wp-123",
        "name": "Test Workplan",
        "status": "active",
        "description": "",
        "tags": [],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create", "--name", "Test Workplan", "--project", "proj-123"])
    assert result.exit_code == 0
    assert "Created workplan wp-123" in result.output
    assert "Test Workplan" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/workplans/", {"name": "Test Workplan", "description": "", "project": "proj-123"}
    )


def test_workplan_create_with_tags(runner, mock_client):
    mock_client.post.return_value = {
        "id": "wp-456",
        "name": "Tagged Plan",
        "status": "active",
        "description": "",
        "tags": ["a", "b"],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["workplan", "create", "--name", "Tagged Plan", "--tags", "a,b", "--project", "proj-456"],
        )
    assert result.exit_code == 0
    assert "Created workplan wp-456" in result.output
    call_data = mock_client.post.call_args[0][1]
    assert call_data["tags"] == ["a", "b"]


def test_workplan_create_with_description(runner, mock_client):
    mock_client.post.return_value = {
        "id": "wp-789",
        "name": "Described Plan",
        "status": "active",
        "description": "My description",
        "tags": [],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["workplan", "create", "--name", "Described Plan", "--description", "My description", "--project", "proj-789"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["description"] == "My description"


def test_workplan_create_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Name is required"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create", "--name", "Fail", "--project", "proj-fail"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


def test_workplan_create_missing_name(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create"])
    assert result.exit_code != 0


# --- list ---

def test_workplan_list_success(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "wp-001", "name": "Plan Alpha", "status": "active"},
        {"id": "wp-002", "name": "Plan Beta", "status": "completed"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list"])
    assert result.exit_code == 0
    assert "wp-001" in result.output
    assert "Plan Alpha" in result.output
    assert "active" in result.output
    assert "wp-002" in result.output
    assert "Plan Beta" in result.output
    assert "ID" in result.output
    assert "Name" in result.output
    assert "Status" in result.output


def test_workplan_list_empty(runner, mock_client):
    mock_client.get.return_value = []
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list"])
    assert result.exit_code == 0
    assert "No workplans found" in result.output


def test_workplan_list_with_status_filter(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "wp-001", "name": "Plan Alpha", "status": "active"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list", "--status", "active"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/v1/workplans/", params={"status": "active"})


def test_workplan_list_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(500, {"error": {"message": "Server error"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list"])
    assert result.exit_code == 1


# --- show ---

def test_workplan_show_success(runner, mock_client):
    mock_client.get.return_value = {
        "id": "wp-abc",
        "name": "Detail Plan",
        "status": "active",
        "description": "A detailed plan",
        "tags": ["infra", "cloud"],
        "created_at": "2025-03-01T10:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "show", "wp-abc"])
    assert result.exit_code == 0
    assert "wp-abc" in result.output
    assert "Detail Plan" in result.output
    assert "active" in result.output
    assert "A detailed plan" in result.output
    assert "infra" in result.output
    assert "cloud" in result.output
    assert "2025-03-01" in result.output
    mock_client.get.assert_called_once_with("/v1/workplans/wp-abc/")


def test_workplan_show_not_found(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "show", "nonexistent"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


def test_workplan_show_no_tags(runner, mock_client):
    mock_client.get.return_value = {
        "id": "wp-notags",
        "name": "No Tags Plan",
        "status": "active",
        "description": "",
        "tags": [],
        "created_at": "2025-03-01T10:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "show", "wp-notags"])
    assert result.exit_code == 0
    assert "Tags:" in result.output


# --- archive ---

def test_workplan_archive_success(runner, mock_client):
    mock_client.post.return_value = {}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "archive", "wp-abc"])
    assert result.exit_code == 0
    assert "Archived workplan wp-abc" in result.output
    mock_client.post.assert_called_once_with("/v1/workplans/wp-abc/archive/")


def test_workplan_archive_not_found(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "archive", "missing-id"])
    assert result.exit_code == 1


# --- complete ---

def test_workplan_complete_success(runner, mock_client):
    mock_client.post.return_value = {}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "complete", "wp-abc"])
    assert result.exit_code == 0
    assert "Completed workplan wp-abc" in result.output
    mock_client.post.assert_called_once_with("/v1/workplans/wp-abc/complete/")


def test_workplan_complete_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(422, {"error": {"message": "Already completed"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "complete", "wp-done"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- workplan stats ---

def test_workplan_stats_success(runner, mock_client):
    mock_client.get.return_value = {
        "total_tasks": 10,
        "completed_percentage": 50,
        "by_status": {"todo": 3, "doing": 2, "done": 5},
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "stats", "wp-abc"])
    assert result.exit_code == 0
    assert "Total tasks: 10" in result.output
    assert "50%" in result.output
    assert "todo: 3" in result.output
    assert "doing: 2" in result.output
    assert "done: 5" in result.output
    mock_client.get.assert_called_once_with("/v1/workplans/wp-abc/stats/")


def test_workplan_stats_no_by_status(runner, mock_client):
    mock_client.get.return_value = {
        "total_tasks": 0,
        "completed_percentage": 0,
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "stats", "wp-empty"])
    assert result.exit_code == 0
    assert "Total tasks: 0" in result.output
    assert "0%" in result.output


def test_workplan_stats_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "stats", "nonexistent"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- milestone stats ---

def test_milestone_stats_success(runner, mock_client):
    mock_client.get.return_value = {
        "total_tasks": 6,
        "completed_percentage": 33,
        "by_status": {"todo": 2, "doing": 2, "done": 2},
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "stats", "ms-abc"])
    assert result.exit_code == 0
    assert "Total tasks: 6" in result.output
    assert "33%" in result.output
    assert "todo: 2" in result.output
    mock_client.get.assert_called_once_with("/v1/milestones/ms-abc/stats/")


def test_milestone_stats_no_by_status(runner, mock_client):
    mock_client.get.return_value = {
        "total_tasks": 0,
        "completed_percentage": 0,
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "stats", "ms-empty"])
    assert result.exit_code == 0
    assert "Total tasks: 0" in result.output


def test_milestone_stats_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "stats", "nonexistent"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


def test_milestone_help(runner):
    result = runner.invoke(cli, ["milestone", "--help"])
    assert result.exit_code == 0
    assert "milestone" in result.output.lower()


# --- milestone create ---

def test_milestone_create_success(runner, mock_client):
    mock_client.post.return_value = {
        "id": "ms-001",
        "name": "Sprint 1",
        "workplan": "wp-abc",
        "description": "",
        "order": 1,
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--name", "Sprint 1", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    assert "ms-001" in result.output
    assert "Sprint 1" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/milestones/", {"name": "Sprint 1", "workplan": "wp-abc"}
    )


def test_milestone_create_with_description_and_order(runner, mock_client):
    mock_client.post.return_value = {
        "id": "ms-002",
        "name": "Sprint 2",
        "workplan": "wp-abc",
        "description": "Second sprint",
        "order": 2,
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            [
                "milestone", "create",
                "--name", "Sprint 2",
                "--workplan", "wp-abc",
                "--description", "Second sprint",
                "--sort-order", "2",
            ],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["description"] == "Second sprint"
    assert call_data["order"] == 2


def test_milestone_create_missing_name(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--workplan", "wp-abc"])
    assert result.exit_code != 0


def test_milestone_create_missing_workplan(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--name", "Sprint 1"])
    assert result.exit_code != 0


def test_milestone_create_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Bad request"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--name", "Fail", "--workplan", "wp-abc"])
    assert result.exit_code == 1
    assert "Error" in result.output


# --- milestone list ---

def test_milestone_list_success(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "ms-001", "name": "Sprint 1", "order": 1, "status": "active"},
        {"id": "ms-002", "name": "Sprint 2", "order": 2, "status": "active"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    assert "ms-001" in result.output
    assert "Sprint 1" in result.output
    assert "ms-002" in result.output
    assert "Sprint 2" in result.output
    mock_client.get.assert_called_once_with("/v1/workplans/wp-abc/milestones/")


def test_milestone_list_empty(runner, mock_client):
    mock_client.get.return_value = []
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    assert "No milestones found" in result.output


def test_milestone_list_missing_workplan(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list"])
    assert result.exit_code != 0


def test_milestone_list_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list", "--workplan", "wp-missing"])
    assert result.exit_code == 1


# --- milestone show ---

def test_milestone_show_success(runner, mock_client):
    mock_client.get.return_value = {
        "id": "ms-001",
        "name": "Sprint 1",
        "workplan": "wp-abc",
        "description": "First sprint",
        "order": 1,
        "status": "active",
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "show", "ms-001"])
    assert result.exit_code == 0
    assert "ms-001" in result.output
    assert "Sprint 1" in result.output
    assert "First sprint" in result.output
    assert "active" in result.output
    mock_client.get.assert_called_once_with("/v1/milestones/ms-001/")


def test_milestone_show_not_found(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "show", "nonexistent"])
    assert result.exit_code == 1
    assert "Error" in result.output


# --- milestone update ---

def test_milestone_update_name(runner, mock_client):
    mock_client.patch.return_value = {
        "id": "ms-001",
        "name": "Updated Sprint",
        "workplan": "wp-abc",
        "description": "",
        "order": 1,
        "status": "active",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001", "--name", "Updated Sprint"])
    assert result.exit_code == 0
    assert "Updated milestone ms-001" in result.output
    mock_client.patch.assert_called_once_with("/v1/milestones/ms-001/", {"name": "Updated Sprint"})


def test_milestone_update_description(runner, mock_client):
    mock_client.patch.return_value = {
        "id": "ms-001",
        "name": "Sprint 1",
        "description": "New desc",
        "order": 1,
        "status": "active",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001", "--description", "New desc"])
    assert result.exit_code == 0
    call_data = mock_client.patch.call_args[0][1]
    assert call_data["description"] == "New desc"


def test_milestone_update_order(runner, mock_client):
    mock_client.patch.return_value = {
        "id": "ms-001",
        "name": "Sprint 1",
        "description": "",
        "order": 5,
        "status": "active",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001", "--sort-order", "5"])
    assert result.exit_code == 0
    call_data = mock_client.patch.call_args[0][1]
    assert call_data["order"] == 5


def test_milestone_update_no_fields(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001"])
    assert result.exit_code == 1
    assert "No fields" in result.output or "nothing" in result.output.lower() or "no fields" in result.output.lower()


def test_milestone_update_api_error(runner, mock_client):
    mock_client.patch.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "missing", "--name", "Fail"])
    assert result.exit_code == 1
    assert "Error" in result.output


# --- help ---

def test_workplan_help(runner):
    result = runner.invoke(cli, ["workplan", "--help"])
    assert result.exit_code == 0
    assert "workplan" in result.output.lower()


def test_workplan_create_help(runner):
    result = runner.invoke(cli, ["workplan", "create", "--help"])
    assert result.exit_code == 0
    assert "--name" in result.output
    assert "--project" in result.output


def test_workplan_create_with_project(runner, mock_client):
    mock_client.post.return_value = {
        "id": "wp-proj",
        "name": "Project Plan",
        "status": "active",
        "description": "",
        "project": "proj-123",
        "tags": [],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["workplan", "create", "--name", "Project Plan", "--project", "proj-123"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["project"] == "proj-123"


def test_workplan_create_missing_project(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create", "--name", "No Project Plan"])
    assert result.exit_code == 1
    assert "project is required" in result.output


def test_workplan_create_with_default_project(runner, mock_client):
    mock_client.post.return_value = {
        "id": "wp-def",
        "name": "Default Project Plan",
        "status": "active",
        "description": "",
        "project": "proj-default",
        "tags": [],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client), \
         patch("vtf.commands.workplan.Config") as mock_config_cls:
        mock_config = mock_config_cls.return_value
        mock_config.project = "proj-default"
        result = runner.invoke(cli, ["workplan", "create", "--name", "Default Project Plan"])
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["project"] == "proj-default"


def test_workplan_list_with_project_filter(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "wp-001", "name": "Plan Alpha", "status": "active"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list", "--project", "proj-123"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/v1/workplans/", params={"project": "proj-123"})
