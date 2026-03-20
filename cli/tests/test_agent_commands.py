import pytest
import yaml
from click.testing import CliRunner
from vtf.cli import cli
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

    original_init = Config.__init__

    def patched_init(self, config_file=None):
        original_init(
            self,
            config_file=str(config_file) if config_file else str(tmp_path / "config.yaml"),
        )

    monkeypatch.setattr(Config, "__init__", patched_init)
    return tmp_path / "config.yaml"


# ── register ────────────────────────────────────────────────────────────────

def test_register_saves_token(runner, requests_mock, isolated_config):
    """register calls POST /v1/agents/ unauthenticated and saves token to config."""
    requests_mock.post(
        "http://localhost:8000/v1/agents/",
        json={"id": "agent-001", "name": "Test Agent", "token": "abc123"},
    )
    result = runner.invoke(cli, ["agent", "register", "--name", "Test Agent"])
    assert result.exit_code == 0, result.output
    assert "agent-001" in result.output
    assert "Token saved to config" in result.output
    # Verify token was persisted to the config file
    with open(isolated_config) as f:
        data = yaml.safe_load(f)
    assert data["token"] == "abc123"


def test_register_with_tags(runner, requests_mock, isolated_config):
    """register sends tags array in request body."""
    mock = requests_mock.post(
        "http://localhost:8000/v1/agents/",
        json={"id": "agent-002", "name": "Tagged Agent", "token": "tok456", "tags": ["x", "y"]},
    )
    result = runner.invoke(cli, ["agent", "register", "--name", "Tagged Agent", "--tags", "x,y"])
    assert result.exit_code == 0, result.output
    assert mock.called
    sent = mock.last_request.json()
    assert sent["tags"] == ["x", "y"]


def test_register_no_auth_header(runner, requests_mock, isolated_config):
    """register must NOT send an Authorization header."""
    mock = requests_mock.post(
        "http://localhost:8000/v1/agents/",
        json={"id": "agent-003", "name": "NoAuth", "token": "t"},
    )
    runner.invoke(cli, ["agent", "register", "--name", "NoAuth"])
    assert "Authorization" not in mock.last_request.headers


def test_register_no_token_in_response(runner, requests_mock, isolated_config):
    """register handles response without a token field gracefully."""
    requests_mock.post(
        "http://localhost:8000/v1/agents/",
        json={"id": "agent-004", "name": "NoToken"},
    )
    result = runner.invoke(cli, ["agent", "register", "--name", "NoToken"])
    assert result.exit_code == 0, result.output
    assert "no token" in result.output.lower()


def test_register_api_error(runner, requests_mock, isolated_config):
    requests_mock.post(
        "http://localhost:8000/v1/agents/",
        status_code=400,
        json={"error": {"message": "Bad request"}},
    )
    result = runner.invoke(cli, ["agent", "register", "--name", "Bad"])
    assert result.exit_code != 0


# ── list ─────────────────────────────────────────────────────────────────────

def test_list_agents_table(runner, requests_mock, isolated_config):
    """list displays agents in table format."""
    requests_mock.get(
        "http://localhost:8000/v1/agents/",
        json=[
            {"id": "aaa-111", "name": "Worker1", "status": "online", "tags": ["ci"]},
            {"id": "bbb-222", "name": "Worker2", "status": "busy", "tags": []},
        ],
    )
    result = runner.invoke(cli, ["agent", "list"])
    assert result.exit_code == 0, result.output
    assert "ID" in result.output
    assert "Name" in result.output
    assert "Status" in result.output
    assert "Worker1" in result.output
    assert "Worker2" in result.output
    assert "online" in result.output
    assert "busy" in result.output
    assert "ci" in result.output


def test_list_agents_status_filter(runner, requests_mock, isolated_config):
    """list --status online sends ?status=online query parameter."""
    mock = requests_mock.get(
        "http://localhost:8000/v1/agents/",
        json=[{"id": "ccc-333", "name": "OnlineAgent", "status": "online", "tags": []}],
    )
    result = runner.invoke(cli, ["agent", "list", "--status", "online"])
    assert result.exit_code == 0, result.output
    assert mock.called
    assert mock.last_request.qs.get("status") == ["online"]


def test_list_agents_empty(runner, requests_mock, isolated_config):
    requests_mock.get("http://localhost:8000/v1/agents/", json=[])
    result = runner.invoke(cli, ["agent", "list"])
    assert result.exit_code == 0
    assert "No agents found" in result.output


# ── show ──────────────────────────────────────────────────────────────────────

def test_show_agent(runner, requests_mock, isolated_config):
    """show displays all agent detail fields."""
    requests_mock.get(
        "http://localhost:8000/v1/agents/agent-x/",
        json={
            "id": "agent-x",
            "name": "DetailAgent",
            "status": "offline",
            "tags": ["gpu", "linux"],
            "registered_at": "2025-01-01T00:00:00Z",
            "last_heartbeat": "2025-01-02T12:00:00Z",
        },
    )
    result = runner.invoke(cli, ["agent", "show", "agent-x"])
    assert result.exit_code == 0, result.output
    assert "agent-x" in result.output
    assert "DetailAgent" in result.output
    assert "offline" in result.output
    assert "gpu" in result.output
    assert "linux" in result.output
    assert "2025-01-01" in result.output
    assert "2025-01-02" in result.output


def test_show_agent_no_heartbeat(runner, requests_mock, isolated_config):
    """show displays 'never' when last_heartbeat is absent."""
    requests_mock.get(
        "http://localhost:8000/v1/agents/agent-new/",
        json={
            "id": "agent-new",
            "name": "NewAgent",
            "status": "online",
            "tags": [],
            "registered_at": "2025-03-01T00:00:00Z",
        },
    )
    result = runner.invoke(cli, ["agent", "show", "agent-new"])
    assert result.exit_code == 0, result.output
    assert "never" in result.output


def test_show_agent_not_found(runner, requests_mock, isolated_config):
    requests_mock.get(
        "http://localhost:8000/v1/agents/missing/",
        status_code=404,
        json={"error": {"message": "Not found"}},
    )
    result = runner.invoke(cli, ["agent", "show", "missing"])
    assert result.exit_code != 0


# ── status ────────────────────────────────────────────────────────────────────

def test_status_set_busy(runner, requests_mock, isolated_config):
    """status --set busy sends PATCH /v1/agents/<id>/ with {status: busy}."""
    mock = requests_mock.patch(
        "http://localhost:8000/v1/agents/agent-x/",
        json={"id": "agent-x", "status": "busy"},
    )
    result = runner.invoke(cli, ["agent", "status", "agent-x", "--set", "busy"])
    assert result.exit_code == 0, result.output
    assert "busy" in result.output
    assert mock.called
    assert mock.last_request.json() == {"status": "busy"}


def test_status_set_online(runner, requests_mock, isolated_config):
    mock = requests_mock.patch(
        "http://localhost:8000/v1/agents/agent-y/",
        json={"id": "agent-y", "status": "online"},
    )
    result = runner.invoke(cli, ["agent", "status", "agent-y", "--set", "online"])
    assert result.exit_code == 0, result.output
    assert "online" in result.output


def test_status_set_offline(runner, requests_mock, isolated_config):
    mock = requests_mock.patch(
        "http://localhost:8000/v1/agents/agent-z/",
        json={"id": "agent-z", "status": "offline"},
    )
    result = runner.invoke(cli, ["agent", "status", "agent-z", "--set", "offline"])
    assert result.exit_code == 0, result.output
    assert "offline" in result.output


def test_status_invalid_choice(runner, isolated_config):
    """status rejects invalid status values."""
    result = runner.invoke(cli, ["agent", "status", "agent-x", "--set", "unknown"])
    assert result.exit_code != 0
    assert "invalid value" in result.output.lower() or "'unknown' is not" in result.output.lower()


def test_status_api_error(runner, requests_mock, isolated_config):
    requests_mock.patch(
        "http://localhost:8000/v1/agents/agent-x/",
        status_code=500,
        json={"error": {"message": "Server error"}},
    )
    result = runner.invoke(cli, ["agent", "status", "agent-x", "--set", "busy"])
    assert result.exit_code != 0
