"""TDD tests for prefs service layer.

Phase 1 of User Management Interfaces: extract business logic into services.
"""

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from prefs.models import (
    AgentLock,
    ChannelProjectMapping,
    ExternalIdentity,
    ProjectMembership,
    UserProfile,
)
from prefs.services import (
    LockConflict,
    acquire_lock,
    add_member,
    check_membership,
    create_channel_mapping,
    delete_channel_mapping,
    link_identity,
    list_channel_mappings,
    list_identities,
    list_locks,
    list_members,
    list_users,
    get_user_detail,
    release_lock,
    remove_member,
    resolve_channel,
    unlink_identity,
    update_member_role,
    update_user_type,
)


# ---------------------------------------------------------------------------
# Lock services
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAcquireLock:
    def test_creates_new_lock(self):
        user = User.objects.create_user("agent1")
        lock = acquire_lock(user, "proj1", "architect")
        assert lock.project_id == "proj1"
        assert lock.role == "architect"
        assert lock.user == user

    def test_reconnects_same_user(self):
        user = User.objects.create_user("agent1")
        lock1 = acquire_lock(user, "proj1", "architect")
        lock2 = acquire_lock(user, "proj1", "architect")
        assert lock1.pk == lock2.pk

    def test_conflict_different_user(self):
        u1 = User.objects.create_user("agent1")
        u2 = User.objects.create_user("agent2")
        acquire_lock(u1, "proj1", "architect")
        with pytest.raises(LockConflict) as exc_info:
            acquire_lock(u2, "proj1", "architect")
        assert exc_info.value.lock.user == u1

    def test_different_roles_no_conflict(self):
        u1 = User.objects.create_user("agent1")
        u2 = User.objects.create_user("agent2")
        acquire_lock(u1, "proj1", "architect")
        lock2 = acquire_lock(u2, "proj1", "executor")
        assert lock2.role == "executor"

    def test_stores_session_id(self):
        user = User.objects.create_user("agent1")
        lock = acquire_lock(user, "proj1", "architect", session_id="sess-123")
        assert lock.session_id == "sess-123"


@pytest.mark.django_db
class TestReleaseLock:
    def test_owner_releases(self):
        user = User.objects.create_user("agent1")
        lock = acquire_lock(user, "proj1", "architect")
        release_lock(lock.pk, user)
        assert not AgentLock.objects.filter(pk=lock.pk).exists()

    def test_non_owner_cannot_release(self):
        u1 = User.objects.create_user("agent1")
        u2 = User.objects.create_user("agent2")
        lock = acquire_lock(u1, "proj1", "architect")
        with pytest.raises(PermissionError):
            release_lock(lock.pk, u2)

    def test_staff_force_release(self):
        agent = User.objects.create_user("agent1")
        staff = User.objects.create_user("admin1", is_staff=True)
        lock = acquire_lock(agent, "proj1", "architect")
        release_lock(lock.pk, staff, force=True)
        assert not AgentLock.objects.filter(pk=lock.pk).exists()

    def test_release_nonexistent_raises(self):
        user = User.objects.create_user("agent1")
        with pytest.raises(AgentLock.DoesNotExist):
            release_lock(9999, user)


@pytest.mark.django_db
class TestListLocks:
    def test_lists_all(self):
        u1 = User.objects.create_user("agent1")
        u2 = User.objects.create_user("agent2")
        acquire_lock(u1, "proj1", "architect")
        acquire_lock(u2, "proj2", "executor")
        locks = list_locks()
        assert len(locks) == 2

    def test_filters_by_project(self):
        u1 = User.objects.create_user("agent1")
        u2 = User.objects.create_user("agent2")
        acquire_lock(u1, "proj1", "architect")
        acquire_lock(u2, "proj2", "executor")
        locks = list_locks(project_id="proj1")
        assert len(locks) == 1
        assert locks[0].project_id == "proj1"


# ---------------------------------------------------------------------------
# Channel mapping services
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestChannelMappingServices:
    def test_create_mapping(self):
        mapping = create_channel_mapping("slack", "C123", "proj1", channel_name="#general")
        assert mapping.provider == "slack"
        assert mapping.channel_id == "C123"
        assert mapping.project_id == "proj1"
        assert mapping.channel_name == "#general"

    def test_resolve_channel_found(self):
        create_channel_mapping("slack", "C123", "proj1")
        result = resolve_channel("slack", "C123")
        assert result == "proj1"

    def test_resolve_channel_not_found(self):
        result = resolve_channel("slack", "MISSING")
        assert result is None

    def test_list_all(self):
        create_channel_mapping("slack", "C1", "proj1")
        create_channel_mapping("slack", "C2", "proj2")
        create_channel_mapping("teams", "T1", "proj3")
        assert len(list_channel_mappings()) == 3

    def test_list_by_provider(self):
        create_channel_mapping("slack", "C1", "proj1")
        create_channel_mapping("teams", "T1", "proj2")
        mappings = list_channel_mappings(provider="slack")
        assert len(mappings) == 1
        assert mappings[0].provider == "slack"

    def test_delete_mapping(self):
        mapping = create_channel_mapping("slack", "C1", "proj1")
        delete_channel_mapping(mapping.pk)
        assert not ChannelProjectMapping.objects.filter(pk=mapping.pk).exists()

    def test_delete_nonexistent_raises(self):
        with pytest.raises(ChannelProjectMapping.DoesNotExist):
            delete_channel_mapping(9999)


# ---------------------------------------------------------------------------
# Identity services
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestIdentityServices:
    def test_link_identity(self):
        user = User.objects.create_user("alice", password="pass")
        identity = link_identity(user, "slack", "U12345", workspace_id="W001")
        assert identity.provider == "slack"
        assert identity.external_id == "U12345"
        assert identity.workspace_id == "W001"
        assert identity.user == user

    def test_list_identities(self):
        user = User.objects.create_user("alice", password="pass")
        link_identity(user, "slack", "U12345")
        link_identity(user, "github", "alice")
        identities = list_identities(user)
        assert len(identities) == 2

    def test_list_identities_filter_provider(self):
        user = User.objects.create_user("alice", password="pass")
        link_identity(user, "slack", "U12345")
        link_identity(user, "github", "alice")
        identities = list_identities(user, provider="slack")
        assert len(identities) == 1
        assert identities[0].provider == "slack"

    def test_unlink_identity(self):
        user = User.objects.create_user("alice", password="pass")
        identity = link_identity(user, "slack", "U12345")
        unlink_identity(identity.pk, user)
        assert not ExternalIdentity.objects.filter(pk=identity.pk).exists()

    def test_unlink_other_users_identity_raises(self):
        alice = User.objects.create_user("alice", password="pass")
        bob = User.objects.create_user("bob", password="pass")
        identity = link_identity(alice, "slack", "U12345")
        with pytest.raises(ExternalIdentity.DoesNotExist):
            unlink_identity(identity.pk, bob)


# ---------------------------------------------------------------------------
# Membership services
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMembershipServices:
    def test_add_member(self):
        user = User.objects.create_user("alice", password="pass")
        membership = add_member("proj1", user.pk, role="member")
        assert membership.project_id == "proj1"
        assert membership.user == user
        assert membership.role == "member"

    def test_add_duplicate_raises(self):
        user = User.objects.create_user("alice", password="pass")
        add_member("proj1", user.pk)
        with pytest.raises(IntegrityError):
            add_member("proj1", user.pk)

    def test_list_members(self):
        u1 = User.objects.create_user("alice", password="pass")
        u2 = User.objects.create_user("bob", password="pass")
        add_member("proj1", u1.pk, role="owner")
        add_member("proj1", u2.pk, role="member")
        members = list_members("proj1")
        assert len(members) == 2

    def test_list_members_empty_project(self):
        members = list_members("empty-project")
        assert len(members) == 0

    def test_update_member_role(self):
        user = User.objects.create_user("alice", password="pass")
        membership = add_member("proj1", user.pk, role="member")
        updated = update_member_role(membership.pk, "owner")
        assert updated.role == "owner"

    def test_update_invalid_membership_raises(self):
        with pytest.raises(ProjectMembership.DoesNotExist):
            update_member_role(9999, "owner")

    def test_remove_member(self):
        user = User.objects.create_user("alice", password="pass")
        membership = add_member("proj1", user.pk)
        remove_member(membership.pk)
        assert not ProjectMembership.objects.filter(pk=membership.pk).exists()

    def test_remove_nonexistent_raises(self):
        with pytest.raises(ProjectMembership.DoesNotExist):
            remove_member(9999)

    def test_check_membership_exists(self):
        user = User.objects.create_user("alice", password="pass")
        add_member("proj1", user.pk, role="owner")
        has_access, role = check_membership(user, "proj1")
        assert has_access is True
        assert role == "owner"

    def test_check_membership_not_member(self):
        user = User.objects.create_user("alice", password="pass")
        has_access, role = check_membership(user, "proj1")
        assert has_access is False
        assert role is None

    def test_check_membership_staff_bypass(self):
        staff = User.objects.create_user("admin", password="pass", is_staff=True)
        has_access, role = check_membership(staff, "any-project")
        assert has_access is True
        assert role == "staff"


# ---------------------------------------------------------------------------
# User services
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUserServices:
    def _make_user(self, username, user_type="human", is_staff=False):
        user = User.objects.create_user(username, password="pass", is_staff=is_staff)
        UserProfile.objects.create(user=user, user_type=user_type)
        return user

    def test_list_users_returns_all(self):
        self._make_user("alice")
        self._make_user("bob")
        users = list_users()
        assert len(users) >= 2

    def test_list_users_search(self):
        self._make_user("alice")
        self._make_user("bob")
        users = list_users(search="ali")
        assert len(users) == 1
        assert users[0].username == "alice"

    def test_list_users_filter_type(self):
        self._make_user("alice", user_type="human")
        self._make_user("bot1", user_type="agent")
        users = list_users(user_type="agent")
        assert all(u.profile.user_type == "agent" for u in users)

    def test_get_user_detail(self):
        user = self._make_user("alice")
        add_member("proj1", user.pk, role="owner")
        detail = get_user_detail(user.pk)
        assert detail.username == "alice"
        assert detail.profile.user_type == "human"
        assert detail.project_memberships.count() == 1

    def test_get_user_detail_not_found(self):
        with pytest.raises(User.DoesNotExist):
            get_user_detail(9999)

    def test_update_user_type(self):
        user = self._make_user("alice", user_type="human")
        profile = update_user_type(user.pk, "service")
        assert profile.user_type == "service"

    def test_update_user_type_invalid(self):
        user = self._make_user("alice")
        with pytest.raises(ValueError):
            update_user_type(user.pk, "invalid_type")
