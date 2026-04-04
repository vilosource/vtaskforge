import pytest
import yaml
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError
from vtf.config import Config


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Provide an isolated config for CLI tests."""
    config_file = tmp_path / "config.yaml"
    monkeypatch.delenv("VTF_API_URL", raising=False)
    monkeypatch.delenv("VTF_TOKEN", raising=False)

    # Patch Config to use tmp config file
    original_init = Config.__init__

    def patched_init(self, config_file=None):
        original_init(self, config_file=str(config_file) if config_file else str(tmp_path / "config.yaml"))

    monkeypatch.setattr(Config, "__init__", patched_init)
    return tmp_path / "config.yaml"


def test_health_success(runner, isolated_config):
    with patch("vtf.cli.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.health.return_value = {"status": "healthy", "checks": {"db": "ok"}}
        mock_get_client.return_value = mock_client
        result = runner.invoke(cli, ["health"])
    assert result.exit_code == 0
    assert "healthy" in result.output.lower()


def test_health_connection_error(runner, isolated_config):
    with patch("vtf.cli.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.health.side_effect = Exception("Connection refused")
        mock_get_client.return_value = mock_client
        result = runner.invoke(cli, ["health"])
    assert result.exit_code == 1
    assert "Connection failed" in result.output or "Connection failed" in (result.output + (result.stderr or ""))


def test_health_api_error(runner, isolated_config):
    with patch("vtf.cli.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.health.side_effect = VtfError("SERVICE_UNAVAILABLE", "Server error")
        mock_get_client.return_value = mock_client
        result = runner.invoke(cli, ["health"])
    assert result.exit_code == 1


def test_config_set_api_url(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "api_url", "http://example.com"])
    assert result.exit_code == 0
    assert "Set api_url" in result.output
    # Verify it was actually written
    assert isolated_config.exists()
    with open(isolated_config) as f:
        data = yaml.safe_load(f)
    assert data["api_url"] == "http://example.com"


def test_config_set_token(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "token", "mytoken123"])
    assert result.exit_code == 0
    assert "Set token" in result.output
    with open(isolated_config) as f:
        data = yaml.safe_load(f)
    assert data["token"] == "mytoken123"


def test_config_show_defaults(runner, isolated_config):
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "api_url: http://localhost:8000" in result.output
    assert "token: not set" in result.output


def test_config_show_with_token(runner, isolated_config):
    # First set a token
    runner.invoke(cli, ["config", "set", "token", "secret"])
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "token: ***" in result.output
    assert "secret" not in result.output


def test_config_show_with_api_url(runner, isolated_config):
    runner.invoke(cli, ["config", "set", "api_url", "http://custom.com"])
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "api_url: http://custom.com" in result.output


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "vtf" in result.output.lower()


def test_health_help(runner):
    result = runner.invoke(cli, ["health", "--help"])
    assert result.exit_code == 0


def test_config_group_help(runner):
    result = runner.invoke(cli, ["config", "--help"])
    assert result.exit_code == 0
    assert "set" in result.output
    assert "show" in result.output


def test_config_show_env_var_api_url(runner, isolated_config, monkeypatch):
    monkeypatch.setenv("VTF_API_URL", "http://from-env.com")
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "http://from-env.com" in result.output


def test_config_set_project(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "project", "proj-123"])
    assert result.exit_code == 0
    assert "Set project" in result.output
    with open(isolated_config) as f:
        data = yaml.safe_load(f)
    assert data["project"] == "proj-123"


def test_config_show_with_project(runner, isolated_config):
    runner.invoke(cli, ["config", "set", "project", "proj-456"])
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "project: proj-456" in result.output


def test_config_show_defaults_includes_project(runner, isolated_config):
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0
    assert "project: not set" in result.output
