import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError
from vtf_sdk.entities import Agent
from tests.sdk_mock_helpers import make_paged


def make_agent(**overrides):
    defaults = {"id": "agt-001", "name": "executor-1", "tags": ["executor"], "status": "online",
                "effective_status": "online", "pod_name": None, "tasks_completed": 0, "tasks_failed": 0}
    defaults.update(overrides)
    return Agent.model_validate(defaults)


@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_client():
    return MagicMock()


def test_agent_list_success(runner, mock_client):
    mock_client.agents.list.return_value = make_paged([
        make_agent(id="agt-001", name="executor-1", status="online", tags=["executor"]),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["agent", "list"])
    assert result.exit_code == 0
    assert "agt-001" in result.output

def test_agent_list_empty(runner, mock_client):
    mock_client.agents.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["agent", "list"])
    assert result.exit_code == 0
    assert "No agents found" in result.output

def test_agent_show_success(runner, mock_client):
    mock_client.agents.get.return_value = make_agent(registered_at="2025-01-01T00:00:00Z")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["agent", "show", "agt-001"])
    assert result.exit_code == 0
    assert "agt-001" in result.output

def test_agent_show_not_found(runner, mock_client):
    mock_client.agents.get.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["agent", "show", "nonexistent"])
    assert result.exit_code == 1

def test_agent_status_success(runner, mock_client):
    mock_client.agents.update_status.return_value = make_agent(status="offline")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["agent", "status", "agt-001", "--set", "offline"])
    assert result.exit_code == 0
    assert "offline" in result.output

def test_agent_register_success(runner):
    mock_reg_client = MagicMock()
    agent = make_agent(id="new-agent", name="my-agent")
    mock_reg_client.agents.register.return_value = (agent, {"id": "new-agent", "token": "tok-123"})
    with patch("vtf.commands.agent.VtfClient", return_value=mock_reg_client):
        result = runner.invoke(cli, ["agent", "register", "--name", "my-agent"])
    assert result.exit_code == 0
    assert "Registered agent new-agent" in result.output

def test_agent_help(runner):
    result = runner.invoke(cli, ["agent", "--help"])
    assert result.exit_code == 0

def test_agent_register_help(runner):
    result = runner.invoke(cli, ["agent", "register", "--help"])
    assert result.exit_code == 0

def test_agent_list_help(runner):
    result = runner.invoke(cli, ["agent", "list", "--help"])
    assert result.exit_code == 0
