"""TDD tests for user management MCP tools.

Phase 2: vtf_whoami, vtf_manage_lock, vtf_resolve_channel,
vtf_list_members, vtf_manage_channel_mapping.

Tests call tool functions directly (not via MCP protocol).
"""
import json

import pytest
from django.contrib.auth.models import User

from prefs.models import AgentLock, ChannelProjectMapping, ProjectMembership, UserProfile
from prefs.services import create_channel_mapping
from mcp_server.tools.identity import (
    vtf_list_members,
    vtf_manage_channel_mapping,
    vtf_manage_lock,
    vtf_resolve_channel,
    vtf_whoami,
)
from mcp_server.user_context import _current_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def agent_user(db):
    user = User.objects.create_user("test-agent")
    UserProfile.objects.create(user=user, user_type="agent")
    return user


@pytest.fixture
def staff_user(db):
    user = User.objects.create_user("admin", password="pass", is_staff=True)
    UserProfile.objects.create(user=user, user_type="human")
    return user


@pytest.fixture(autouse=True)
def clear_user_context():
    """Reset user context between tests."""
    _current_user.set(None)
    yield
    _current_user.set(None)


# ---------------------------------------------------------------------------
# vtf_whoami
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWhoami:
    def test_returns_identity(self, agent_user):
        _current_user.set(agent_user)
        result = json.loads(vtf_whoami())
        assert result["success"] is True
        data = result["data"]
        assert data["username"] == "test-agent"
        assert data["user_type"] == "agent"
        assert data["is_staff"] is False

    def test_includes_projects(self, agent_user):
        _current_user.set(agent_user)
        ProjectMembership.objects.create(user=agent_user, project_id="proj1", role="member")
        result = json.loads(vtf_whoami())
        projects = result["data"]["projects"]
        assert len(projects) == 1
        # v2 format: project is a nested ref object
        assert projects[0]["project"]["id"] == "proj1"
        assert projects[0]["role"] == "member"

    def test_no_user_context_returns_error(self):
        result = json.loads(vtf_whoami())
        assert result["success"] is False


# ---------------------------------------------------------------------------
# vtf_manage_lock
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestManageLock:
    def test_acquire_lock(self, agent_user):
        _current_user.set(agent_user)
        result = json.loads(vtf_manage_lock(action="acquire", project_id="proj1", role="architect"))
        assert result["success"] is True
        assert result["data"]["project_id"] == "proj1"
        assert result["data"]["role"] == "architect"
        assert AgentLock.objects.filter(project_id="proj1", role="architect").exists()

    def test_list_locks(self, agent_user):
        _current_user.set(agent_user)
        AgentLock.objects.create(project_id="proj1", role="architect", user=agent_user)
        result = json.loads(vtf_manage_lock(action="list"))
        assert result["success"] is True
        assert len(result["data"]["locks"]) == 1

    def test_list_locks_filter_project(self, agent_user):
        other = User.objects.create_user("other-agent")
        _current_user.set(agent_user)
        AgentLock.objects.create(project_id="proj1", role="architect", user=agent_user)
        AgentLock.objects.create(project_id="proj2", role="executor", user=other)
        result = json.loads(vtf_manage_lock(action="list", project_id="proj1"))
        assert len(result["data"]["locks"]) == 1

    def test_release_lock(self, agent_user):
        _current_user.set(agent_user)
        lock = AgentLock.objects.create(project_id="proj1", role="architect", user=agent_user)
        result = json.loads(vtf_manage_lock(action="release", lock_id=lock.pk))
        assert result["success"] is True
        assert not AgentLock.objects.filter(pk=lock.pk).exists()

    def test_acquire_conflict(self, agent_user):
        other = User.objects.create_user("other-agent")
        AgentLock.objects.create(project_id="proj1", role="architect", user=other)
        _current_user.set(agent_user)
        result = json.loads(vtf_manage_lock(action="acquire", project_id="proj1", role="architect"))
        assert result["success"] is False
        assert "locked" in result["message"].lower() or "conflict" in result["message"].lower()

    def test_acquire_missing_params(self, agent_user):
        _current_user.set(agent_user)
        result = json.loads(vtf_manage_lock(action="acquire"))
        assert result["success"] is False

    def test_invalid_action(self, agent_user):
        _current_user.set(agent_user)
        result = json.loads(vtf_manage_lock(action="invalid"))
        assert result["success"] is False


# ---------------------------------------------------------------------------
# vtf_resolve_channel
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestResolveChannel:
    def test_resolves_existing(self):
        create_channel_mapping("slack", "C123", "proj1", channel_name="#general")
        result = json.loads(vtf_resolve_channel(provider="slack", channel_id="C123"))
        assert result["success"] is True
        assert result["data"]["project_id"] == "proj1"

    def test_not_found(self):
        result = json.loads(vtf_resolve_channel(provider="slack", channel_id="MISSING"))
        assert result["success"] is False


# ---------------------------------------------------------------------------
# vtf_list_members
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestListMembers:
    def test_lists_members(self, agent_user):
        _current_user.set(agent_user)
        user = User.objects.create_user("alice", password="pass")
        ProjectMembership.objects.create(user=user, project_id="proj1", role="owner")
        ProjectMembership.objects.create(user=agent_user, project_id="proj1", role="member")
        result = json.loads(vtf_list_members(project_id="proj1"))
        assert result["success"] is True
        assert len(result["data"]["members"]) == 2

    def test_empty_project(self):
        result = json.loads(vtf_list_members(project_id="empty"))
        assert result["success"] is True
        assert len(result["data"]["members"]) == 0

    def test_uses_default_project(self, agent_user):
        """Falls back to project context when project_id is omitted."""
        from mcp_server.project_context import _current_project
        _current_project.set("proj1")
        _current_user.set(agent_user)
        ProjectMembership.objects.create(user=agent_user, project_id="proj1", role="member")
        result = json.loads(vtf_list_members())
        assert result["success"] is True
        assert len(result["data"]["members"]) == 1
        _current_project.set(None)


# ---------------------------------------------------------------------------
# vtf_manage_channel_mapping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestManageChannelMapping:
    def test_list_mappings(self, staff_user):
        _current_user.set(staff_user)
        create_channel_mapping("slack", "C1", "proj1")
        create_channel_mapping("slack", "C2", "proj2")
        result = json.loads(vtf_manage_channel_mapping(action="list"))
        assert result["success"] is True
        assert len(result["data"]["mappings"]) == 2

    def test_list_filter_provider(self, staff_user):
        _current_user.set(staff_user)
        create_channel_mapping("slack", "C1", "proj1")
        create_channel_mapping("teams", "T1", "proj2")
        result = json.loads(vtf_manage_channel_mapping(action="list", provider="slack"))
        assert len(result["data"]["mappings"]) == 1

    def test_create_mapping(self, staff_user):
        _current_user.set(staff_user)
        result = json.loads(vtf_manage_channel_mapping(
            action="create", provider="slack", channel_id="C123",
            project_id="proj1", channel_name="#general",
        ))
        assert result["success"] is True
        assert ChannelProjectMapping.objects.filter(channel_id="C123").exists()

    def test_create_missing_params(self, staff_user):
        _current_user.set(staff_user)
        result = json.loads(vtf_manage_channel_mapping(action="create", provider="slack"))
        assert result["success"] is False

    def test_delete_mapping(self, staff_user):
        _current_user.set(staff_user)
        mapping = create_channel_mapping("slack", "C1", "proj1")
        result = json.loads(vtf_manage_channel_mapping(action="delete", mapping_id=mapping.pk))
        assert result["success"] is True
        assert not ChannelProjectMapping.objects.filter(pk=mapping.pk).exists()

    def test_delete_nonexistent(self, staff_user):
        _current_user.set(staff_user)
        result = json.loads(vtf_manage_channel_mapping(action="delete", mapping_id=9999))
        assert result["success"] is False

    def test_invalid_action(self, staff_user):
        _current_user.set(staff_user)
        result = json.loads(vtf_manage_channel_mapping(action="invalid"))
        assert result["success"] is False
