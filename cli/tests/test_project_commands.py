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

def test_project_list_success(runner, mock_client):
    mock_client.get.return_value = [
        {"id": "proj-001", "name": "vtaskforge", "status": "active"},
        {"id": "proj-002", "name": "platform-migration", "status": "active"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "list"])
    assert result.exit_code == 0
    assert "proj-001" in result.output
    assert "vtaskforge" in result.output
    assert "active" in result.output
    assert "proj-002" in result.output
    assert "platform-migration" in result.output
    assert "ID" in result.output
    assert "Name" in result.output
    assert "Status" in result.output


def test_project_list_empty(runner, mock_client):
    mock_client.get.return_value = []
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "list"])
    assert result.exit_code == 0
    assert "No projects found" in result.output


def test_project_list_long_name_truncated(runner, mock_client):
    long_name = "A" * 40
    mock_client.get.return_value = [
        {"id": "proj-001", "name": long_name, "status": "active"},
    ]
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "list"])
    assert result.exit_code == 0
    assert ".." in result.output


def test_project_list_api_error(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(500, {"error": {"message": "Server error"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "list"])
    assert result.exit_code == 1


# --- create ---

def test_project_create_success(runner, mock_client):
    mock_client.post.return_value = {
        "id": "proj-123",
        "name": "Test Project",
        "status": "active",
        "description": "",
        "tags": [],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "create", "--name", "Test Project"])
    assert result.exit_code == 0
    assert "Created project proj-123" in result.output
    assert "Test Project" in result.output
    mock_client.post.assert_called_once_with(
        "/v1/projects/", {"name": "Test Project"}
    )


def test_project_create_with_repo(runner, mock_client):
    mock_client.post.return_value = {
        "id": "proj-456",
        "name": "Repo Project",
        "status": "active",
        "description": "",
        "repo_url": "git@github.com:test/repo.git",
        "tags": [],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["project", "create", "--name", "Repo Project", "--repo", "git@github.com:test/repo.git"],
        )
    assert result.exit_code == 0
    assert "Created project proj-456" in result.output
    call_data = mock_client.post.call_args[0][1]
    assert call_data["repo_url"] == "git@github.com:test/repo.git"


def test_project_create_with_tags(runner, mock_client):
    mock_client.post.return_value = {
        "id": "proj-789",
        "name": "Tagged Project",
        "status": "active",
        "description": "",
        "tags": ["backend", "infra"],
        "created_at": "2025-01-01T00:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["project", "create", "--name", "Tagged Project", "--tags", "backend,infra"],
        )
    assert result.exit_code == 0
    call_data = mock_client.post.call_args[0][1]
    assert call_data["tags"] == ["backend", "infra"]


def test_project_create_missing_name(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "create"])
    assert result.exit_code != 0


def test_project_create_api_error(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(400, {"error": {"message": "Name is required"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "create", "--name", "Fail"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- show ---

def test_project_show_success(runner, mock_client):
    mock_client.get.return_value = {
        "id": "proj-abc",
        "name": "Detailed Project",
        "status": "active",
        "description": "A project with details",
        "repo_url": "git@github.com:test/detailed.git",
        "default_branch": "develop",
        "tags": ["backend", "api"],
        "created_at": "2025-03-01T10:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "show", "proj-abc"])
    assert result.exit_code == 0
    assert "proj-abc" in result.output
    assert "Detailed Project" in result.output
    assert "active" in result.output
    assert "A project with details" in result.output
    assert "git@github.com:test/detailed.git" in result.output
    assert "develop" in result.output
    assert "backend" in result.output
    assert "api" in result.output
    assert "2025-03-01" in result.output
    mock_client.get.assert_called_once_with("/v1/projects/proj-abc/")


def test_project_show_minimal(runner, mock_client):
    mock_client.get.return_value = {
        "id": "proj-min",
        "name": "Minimal Project",
        "status": "active",
        "description": "",
        "repo_url": "",
        "tags": [],
        "created_at": "2025-03-01T10:00:00Z",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "show", "proj-min"])
    assert result.exit_code == 0
    assert "proj-min" in result.output
    assert "Minimal Project" in result.output
    assert "main" in result.output  # default branch


def test_project_show_not_found(runner, mock_client):
    mock_client.get.side_effect = VTFAPIError(404, {"error": {"message": "Not found"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "show", "nonexistent"])
    assert result.exit_code == 1
    assert "Error" in result.output or "Error" in (result.output + (result.stderr or ""))


# --- help ---

def test_project_help(runner):
    result = runner.invoke(cli, ["project", "--help"])
    assert result.exit_code == 0
    assert "project" in result.output.lower()


def test_project_create_help(runner):
    result = runner.invoke(cli, ["project", "create", "--help"])
    assert result.exit_code == 0
    assert "--name" in result.output
    assert "--repo" in result.output
    assert "--tags" in result.output