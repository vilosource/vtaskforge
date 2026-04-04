"""TDD tests for user management CLI commands.

Phase 3: vtf user, vtf member, vtf lock, vtf channel-mapping, vtf service-account.
Uses MagicMock client + Click CliRunner (no live API).
"""

from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


# ---------------------------------------------------------------------------
# vtf user
# ---------------------------------------------------------------------------


class TestUserList:
    def test_lists_users(self, runner, mock_client):
        mock_client.get.return_value = {"results": [
            {"id": 1, "username": "alice", "user_type": "human", "is_staff": False, "last_login": "2026-04-01"},
            {"id": 2, "username": "bot1", "user_type": "agent", "is_staff": False, "last_login": None},
        ]}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "list"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "bot1" in result.output
        assert "human" in result.output
        assert "agent" in result.output

    def test_search_filter(self, runner, mock_client):
        mock_client.get.return_value = {"results": [
            {"id": 1, "username": "alice", "user_type": "human", "is_staff": False, "last_login": None},
        ]}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "list", "--search", "ali"])
        assert result.exit_code == 0
        assert "alice" in result.output
        mock_client.get.assert_called_once_with("/v1/users/", params={"search": "ali"})

    def test_type_filter(self, runner, mock_client):
        mock_client.get.return_value = {"results": [
            {"id": 2, "username": "bot1", "user_type": "agent", "is_staff": False, "last_login": None},
        ]}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "list", "--type", "agent"])
        assert result.exit_code == 0
        assert "bot1" in result.output
        mock_client.get.assert_called_once_with("/v1/users/", params={"user_type": "agent"})

    def test_empty_list(self, runner, mock_client):
        mock_client.get.return_value = {"results": []}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "list"])
        assert result.exit_code == 0
        assert "No users found" in result.output


class TestUserShow:
    def test_shows_detail(self, runner, mock_client):
        mock_client.get.return_value = {
            "id": 1, "username": "alice", "user_type": "human",
            "is_staff": True, "is_active": True,
            "date_joined": "2026-01-15", "last_login": "2026-04-01",
            "memberships": [
                {"id": 1, "project_id": "proj1", "username": "alice", "role": "owner", "created_at": "2026-01-15"},
            ],
        }
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "show", "1"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "human" in result.output
        assert "proj1" in result.output
        assert "owner" in result.output

    def test_not_found(self, runner, mock_client):
        mock_client.get.side_effect = VtfError("UNKNOWN", 404, {"detail": "Not found."})
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["user", "show", "999"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# vtf member
# ---------------------------------------------------------------------------


class TestMemberList:
    def test_lists_members(self, runner, mock_client):
        mock_client.get.return_value = {"results": [
            {"id": 1, "user_id": 1, "username": "alice", "role": "owner", "created_at": "2026-01-15"},
            {"id": 2, "user_id": 2, "username": "bob", "role": "member", "created_at": "2026-02-01"},
        ]}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["member", "list", "proj1"])
        assert result.exit_code == 0
        assert "alice" in result.output
        assert "bob" in result.output
        assert "owner" in result.output


class TestMemberAdd:
    def test_adds_member(self, runner, mock_client):
        mock_client.post.return_value = {"id": 3, "user_id": 3, "username": "charlie", "role": "member"}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["member", "add", "proj1", "charlie"])
        assert result.exit_code == 0
        assert "charlie" in result.output
        assert "member" in result.output

    def test_adds_with_role(self, runner, mock_client):
        mock_client.post.return_value = {"id": 3, "user_id": 3, "username": "charlie", "role": "viewer"}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["member", "add", "proj1", "charlie", "--role", "viewer"])
        assert result.exit_code == 0
        assert "viewer" in result.output

    def test_duplicate_returns_error(self, runner, mock_client):
        mock_client.post.side_effect = VtfError("UNKNOWN", 409, {"detail": "Already a member."})
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["member", "add", "proj1", "charlie"])
        assert result.exit_code == 1


class TestMemberRemove:
    def test_removes_member(self, runner, mock_client):
        mock_client.delete.return_value = {}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["member", "remove", "proj1", "3"])
        assert result.exit_code == 0
        assert "Removed" in result.output


# ---------------------------------------------------------------------------
# vtf lock
# ---------------------------------------------------------------------------


class TestLockList:
    def test_lists_locks(self, runner, mock_client):
        mock_client.get.return_value = {"results": [
            {"id": 1, "project_id": "proj1", "role": "architect", "user": "agent-1",
             "created_at": "2026-04-01T10:00:00Z", "last_activity": "2026-04-01T11:00:00Z"},
        ]}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["lock", "list"])
        assert result.exit_code == 0
        assert "proj1" in result.output
        assert "architect" in result.output
        assert "agent-1" in result.output

    def test_filter_by_project(self, runner, mock_client):
        mock_client.get.return_value = {"results": [
            {"id": 1, "project_id": "proj1", "role": "architect", "user": "agent-1",
             "created_at": "2026-04-01T10:00:00Z", "last_activity": "2026-04-01T11:00:00Z"},
        ]}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["lock", "list", "--project", "proj1"])
        assert result.exit_code == 0
        mock_client.get.assert_called_once_with("/v1/locks/", params={"project_id": "proj1"})

    def test_empty(self, runner, mock_client):
        mock_client.get.return_value = {"results": []}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["lock", "list"])
        assert result.exit_code == 0
        assert "No active locks" in result.output


class TestLockRelease:
    def test_releases_lock(self, runner, mock_client):
        mock_client.delete.return_value = {}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["lock", "release", "1"])
        assert result.exit_code == 0
        assert "Released" in result.output

    def test_not_found(self, runner, mock_client):
        mock_client.delete.side_effect = VtfError("UNKNOWN", 404, {"detail": "Not found."})
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["lock", "release", "999"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# vtf channel-mapping
# ---------------------------------------------------------------------------


class TestChannelMappingList:
    def test_lists_mappings(self, runner, mock_client):
        mock_client.get.return_value = {"results": [
            {"id": 1, "provider": "slack", "channel_id": "C123", "channel_name": "#general",
             "project_id": "proj1"},
        ]}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["channel-mapping", "list"])
        assert result.exit_code == 0
        assert "slack" in result.output
        assert "#general" in result.output
        assert "proj1" in result.output


class TestChannelMappingCreate:
    def test_creates_mapping(self, runner, mock_client):
        mock_client.post.return_value = {
            "id": 2, "provider": "slack", "channel_id": "C456",
            "project_id": "proj2",
        }
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, [
                "channel-mapping", "create",
                "--provider", "slack",
                "--channel-id", "C456",
                "--project", "proj2",
            ])
        assert result.exit_code == 0
        assert "proj2" in result.output


class TestChannelMappingDelete:
    def test_deletes_mapping(self, runner, mock_client):
        mock_client.delete.return_value = {}
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["channel-mapping", "delete", "1"])
        assert result.exit_code == 0
        assert "Deleted" in result.output


# ---------------------------------------------------------------------------
# vtf service-account
# ---------------------------------------------------------------------------


class TestServiceAccountCreate:
    def test_creates_account(self, runner, mock_client):
        mock_client.post.return_value = {
            "id": 10, "username": "ci-bot", "token": "abc123def456", "user_type": "service",
        }
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["service-account", "create", "ci-bot"])
        assert result.exit_code == 0
        assert "ci-bot" in result.output
        assert "abc123def456" in result.output

    def test_duplicate_returns_error(self, runner, mock_client):
        mock_client.post.side_effect = VtfError("UNKNOWN", 400, {"detail": "Already exists."})
        with patch("vtf.cli.get_client", return_value=mock_client):
            result = runner.invoke(cli, ["service-account", "create", "ci-bot"])
        assert result.exit_code == 1
