import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError
from tests.sdk_mock_helpers import make_project, make_paged, make_vtf_error


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


# --- list ---

def test_project_list_success(runner, mock_client):
    mock_client.projects.list.return_value = make_paged([
        make_project(id="proj-001", name="vtaskforge", status="active"),
        make_project(id="proj-002", name="platform-migration", status="active"),
    ])
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
    mock_client.projects.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "list"])
    assert result.exit_code == 0
    assert "No projects found" in result.output


def test_project_list_long_name_truncated(runner, mock_client):
    long_name = "A" * 40
    mock_client.projects.list.return_value = make_paged([
        make_project(id="proj-001", name=long_name, status="active"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "list"])
    assert result.exit_code == 0
    assert ".." in result.output


def test_project_list_api_error(runner, mock_client):
    mock_client.projects.list.side_effect = VtfError("UNKNOWN", "Server error")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "list"])
    assert result.exit_code == 1


# --- create ---

def test_project_create_success(runner, mock_client):
    mock_client.projects.create.return_value = make_project(id="proj-123", name="Test Project")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "create", "--name", "Test Project"])
    assert result.exit_code == 0
    assert "Created project proj-123" in result.output
    assert "Test Project" in result.output


def test_project_create_with_repo(runner, mock_client):
    mock_client.projects.create.return_value = make_project(id="proj-456", name="Repo Project")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["project", "create", "--name", "Repo Project", "--repo", "git@github.com:test/repo.git"],
        )
    assert result.exit_code == 0
    assert "Created project proj-456" in result.output
    mock_client.projects.create.assert_called_once()
    call_kwargs = mock_client.projects.create.call_args[1]
    assert call_kwargs["repo_url"] == "git@github.com:test/repo.git"


def test_project_create_with_tags(runner, mock_client):
    mock_client.projects.create.return_value = make_project(id="proj-789", name="Tagged Project")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(
            cli,
            ["project", "create", "--name", "Tagged Project", "--tags", "backend,infra"],
        )
    assert result.exit_code == 0
    call_kwargs = mock_client.projects.create.call_args[1]
    assert call_kwargs["tags"] == ["backend", "infra"]


def test_project_create_missing_name(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "create"])
    assert result.exit_code != 0


def test_project_create_api_error(runner, mock_client):
    mock_client.projects.create.side_effect = VtfError("VALIDATION_ERROR", "Name is required")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "create", "--name", "Fail"])
    assert result.exit_code == 1


# --- show ---

def test_project_show_success(runner, mock_client):
    mock_client.projects.get.return_value = make_project(
        id="proj-abc", name="Detailed Project", status="active",
        description="A project with details",
        repo_url="git@github.com:test/detailed.git",
        default_branch="develop",
        tags=["backend", "api"],
    )
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


def test_project_show_minimal(runner, mock_client):
    mock_client.projects.get.return_value = make_project(
        id="proj-min", name="Minimal Project", status="active",
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "show", "proj-min"])
    assert result.exit_code == 0
    assert "proj-min" in result.output
    assert "Minimal Project" in result.output
    assert "main" in result.output


def test_project_show_not_found(runner, mock_client):
    from vtf_sdk.exceptions import NotFound
    mock_client.projects.get.side_effect = NotFound("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["project", "show", "nonexistent"])
    assert result.exit_code == 1


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
