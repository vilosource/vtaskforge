"""Tests for user management CLI commands (user, member, lock, channel-mapping, service-account)."""
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError
from tests.sdk_mock_helpers import make_paged


@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_client():
    return MagicMock()


# --- vtf user ---

def test_user_list_success(runner, mock_client):
    mock_client.users.list.return_value = make_paged([
        {"id": 1, "username": "admin", "user_type": "human", "is_staff": True, "last_login": "2025-01-01"},
        {"id": 2, "username": "agent-1", "user_type": "agent", "is_staff": False, "last_login": None},
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["user", "list"])
    assert result.exit_code == 0
    assert "admin" in result.output

def test_user_list_empty(runner, mock_client):
    mock_client.users.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["user", "list"])
    assert result.exit_code == 0
    assert "No users found" in result.output

def test_user_show_success(runner, mock_client):
    mock_client.users.get.return_value = {
        "username": "admin", "user_type": "human", "is_staff": True,
        "is_active": True, "date_joined": "2025-01-01", "last_login": "2025-04-01",
        "memberships": [{"project": {"id": "p1", "name": "Proj"}, "role": "owner"}],
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["user", "show", "1"])
    assert result.exit_code == 0
    assert "admin" in result.output

def test_user_show_not_found(runner, mock_client):
    mock_client.users.get.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["user", "show", "999"])
    assert result.exit_code == 1


# --- vtf member ---

def test_member_list_success(runner, mock_client):
    mock_client.members.list.return_value = make_paged([
        {"id": 1, "user": {"type": "user", "id": "1", "username": "admin"}, "role": "owner", "created_at": "2025-01-01"},
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["member", "list", "proj-1"])
    assert result.exit_code == 0

def test_member_add_success(runner, mock_client):
    mock_client.members.add.return_value = {
        "user": {"type": "user", "id": "2", "username": "newuser"}, "role": "member",
    }
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["member", "add", "proj-1", "newuser"])
    assert result.exit_code == 0
    assert "newuser" in result.output

def test_member_set_role_success(runner, mock_client):
    mock_client.members.set_role.return_value = {"role": "viewer"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["member", "set-role", "proj-1", "1", "viewer"])
    assert result.exit_code == 0

def test_member_remove_success(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["member", "remove", "proj-1", "1"])
    assert result.exit_code == 0
    assert "Removed" in result.output


# --- vtf lock ---

def test_lock_list_success(runner, mock_client):
    mock_client.locks.list.return_value = make_paged([
        {"id": 1, "project": {"id": "p1", "name": "Proj"}, "role": "architect",
         "user": {"type": "user", "id": "1", "username": "admin"}, "created_at": "2025-01-01"},
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["lock", "list"])
    assert result.exit_code == 0

def test_lock_list_empty(runner, mock_client):
    mock_client.locks.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["lock", "list"])
    assert result.exit_code == 0
    assert "No active locks" in result.output

def test_lock_release_success(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["lock", "release", "1"])
    assert result.exit_code == 0
    assert "Released lock 1" in result.output


# --- vtf channel-mapping ---

def test_channel_mapping_list_success(runner, mock_client):
    mock_client.channel_mappings.list.return_value = make_paged([
        {"id": 1, "provider": "slack", "channel_id": "C123", "channel_name": "#dev",
         "project": {"id": "p1", "name": "Proj"}},
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["channel-mapping", "list"])
    assert result.exit_code == 0

def test_channel_mapping_list_empty(runner, mock_client):
    mock_client.channel_mappings.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["channel-mapping", "list"])
    assert result.exit_code == 0
    assert "No channel mappings" in result.output

def test_channel_mapping_create_success(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["channel-mapping", "create", "--provider", "slack", "--channel-id", "C123", "--project", "p1"])
    assert result.exit_code == 0
    assert "Created mapping" in result.output

def test_channel_mapping_delete_success(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["channel-mapping", "delete", "1"])
    assert result.exit_code == 0
    assert "Deleted mapping 1" in result.output


# --- vtf service-account ---

def test_service_account_create_success(runner, mock_client):
    mock_client.service_accounts.create.return_value = {"username": "svc-test", "token": "secret-token-123"}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["service-account", "create", "svc-test"])
    assert result.exit_code == 0
    assert "svc-test" in result.output
    assert "secret-token-123" in result.output


# --- help ---

def test_user_help(runner):
    result = runner.invoke(cli, ["user", "--help"])
    assert result.exit_code == 0

def test_member_help(runner):
    result = runner.invoke(cli, ["member", "--help"])
    assert result.exit_code == 0

def test_lock_help(runner):
    result = runner.invoke(cli, ["lock", "--help"])
    assert result.exit_code == 0

def test_channel_mapping_help(runner):
    result = runner.invoke(cli, ["channel-mapping", "--help"])
    assert result.exit_code == 0

def test_service_account_help(runner):
    result = runner.invoke(cli, ["service-account", "--help"])
    assert result.exit_code == 0
