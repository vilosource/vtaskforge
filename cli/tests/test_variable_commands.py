"""CLI tests for `vtf project var …` and `vtf task lint` (C.2 Slice 5)."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vtf.cli import cli
from tests.sdk_mock_helpers import make_paged, make_project_variable, make_vtf_error


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


# --- vtf project var list ---

def test_var_list(runner, mock_client):
    mock_client.project_variables.list.return_value = make_paged([
        make_project_variable(id="v1", name="GH_TOKEN", role="executor"),
        make_project_variable(id="v2", name="LLM_KEY", role="judge", scope="shared"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "list", "abad"])
    assert r.exit_code == 0
    assert "GH_TOKEN" in r.output and "executor" in r.output
    assert "LLM_KEY" in r.output
    mock_client.project_variables.list.assert_called_once()


def test_var_list_empty(runner, mock_client):
    mock_client.project_variables.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "list", "abad"])
    assert r.exit_code == 0
    assert "No variables" in r.output


# --- vtf project var add ---

def test_var_add(runner, mock_client):
    mock_client.project_variables.create.return_value = make_project_variable(
        id="v1", name="GH_TOKEN", role="executor")
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "add", "abad", "GH_TOKEN", "--role", "executor"])
    assert r.exit_code == 0
    assert "GH_TOKEN" in r.output
    _, kwargs = mock_client.project_variables.create.call_args
    assert kwargs["name"] == "GH_TOKEN" and kwargs["role"] == "executor"


def test_var_add_force(runner, mock_client):
    mock_client.project_variables.create.return_value = make_project_variable(id="v1")
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "add", "abad", "GH_TOKE", "--role", "executor", "--force"])
    assert r.exit_code == 0
    _, kwargs = mock_client.project_variables.create.call_args
    assert kwargs["force"] is True


def test_var_add_error(runner, mock_client):
    mock_client.project_variables.create.side_effect = make_vtf_error("duplicate", "DUPLICATE")
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "add", "abad", "X", "--role", "executor"])
    assert r.exit_code == 1
    assert "Error" in r.output


# --- vtf project var show / update / remove (resolve name+role -> pk) ---

def test_var_show(runner, mock_client):
    mock_client.project_variables.list.return_value = make_paged([
        make_project_variable(id="v1", name="GH_TOKEN", role="executor", description="gh creds"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "show", "abad", "GH_TOKEN", "--role", "executor"])
    assert r.exit_code == 0
    assert "GH_TOKEN" in r.output and "gh creds" in r.output


def test_var_update(runner, mock_client):
    mock_client.project_variables.list.return_value = make_paged([
        make_project_variable(id="v1", name="GH_TOKEN", role="executor"),
    ])
    mock_client.project_variables.update.return_value = make_project_variable(
        id="v1", name="GH_TOKEN", role="executor", required=False)
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "update", "abad", "GH_TOKEN",
                                "--role", "executor", "--not-required"])
    assert r.exit_code == 0
    args, kwargs = mock_client.project_variables.update.call_args
    assert args[0] == "abad" and args[1] == "v1"
    assert kwargs.get("required") is False


def test_var_remove(runner, mock_client):
    mock_client.project_variables.list.return_value = make_paged([
        make_project_variable(id="v1", name="GH_TOKEN", role="executor"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "remove", "abad", "GH_TOKEN", "--role", "executor"])
    assert r.exit_code == 0
    mock_client.project_variables.delete.assert_called_once_with("abad", "v1")


def test_var_remove_not_found(runner, mock_client):
    mock_client.project_variables.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["project", "var", "remove", "abad", "NOPE", "--role", "executor"])
    assert r.exit_code == 1
    assert "not found" in r.output.lower()


# --- vtf task lint ---

def test_task_lint_clean(runner, mock_client, tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text("variables:\n  - name: GH_TOKEN\n")
    mock_client.project_variables.list.return_value = make_paged([
        make_project_variable(id="v1", name="GH_TOKEN", role="executor"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["task", "lint", str(spec), "--project", "abad"])
    assert r.exit_code == 0
    assert "ok" in r.output.lower() or "pass" in r.output.lower()


def test_task_lint_near_miss(runner, mock_client, tmp_path):
    spec = tmp_path / "spec.yaml"
    spec.write_text("variables:\n  - name: GH_TOKE\n")
    mock_client.project_variables.list.return_value = make_paged([
        make_project_variable(id="v1", name="GH_TOKEN", role="executor"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        r = runner.invoke(cli, ["task", "lint", str(spec), "--project", "abad"])
    assert r.exit_code == 1
    assert "GH_TOKEN" in r.output  # suggests the near match
