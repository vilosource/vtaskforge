import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf.client import VTFAPIError
from vtf.config import Config


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
        result = runner.invoke(cli, ["workplan", "create", "--name", "Test Workplan"])
    assert result.exit_code == 0
    assert "Created workplan wp-123" in result.output
    assert "Test Workplan" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/workplans/", {"name": "Test Workplan", "description": ""}
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
            ["workplan", "create", "--name", "Tagged Plan", "--tags", "a,b"],
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
            ["workplan", "create", "--name", "Described Plan", "--description", "My description"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["description"] == "My description"


def test_workplan_create_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Name is required"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create", "--name", "Fail"])
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


# --- help ---

def test_workplan_help(runner):
    result = runner.invoke(cli, ["workplan", "--help"])
    assert result.exit_code == 0
    assert "workplan" in result.output.lower()


def test_workplan_create_help(runner):
    result = runner.invoke(cli, ["workplan", "create", "--help"])
    assert result.exit_code == 0
    assert "--name" in result.output
