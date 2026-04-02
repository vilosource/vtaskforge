"""Service layer for user preferences and activity tracking."""

from django.contrib.auth.models import User
from django.db.models import QuerySet
from rest_framework.authtoken.models import Token

from .models import (
    AgentLock,
    ChannelProjectMapping,
    ExternalIdentity,
    ProjectMembership,
    RecentAccess,
    UserProfile,
)

MAX_RECENT = 20

VALID_USER_TYPES = {t[0] for t in UserProfile.USER_TYPES}


# ---------------------------------------------------------------------------
# Recent access
# ---------------------------------------------------------------------------


def record_access(user, resource_type: str, resource_id: str, title: str, status: str = "") -> None:
    """Record that a user accessed a resource. Upsert + trim to MAX_RECENT."""
    if user.is_anonymous:
        return

    if not user.has_usable_password():
        return  # Agent user — don't track

    RecentAccess.objects.update_or_create(
        user=user,
        resource_type=resource_type,
        resource_id=resource_id,
        defaults={
            "resource_title": title[:255],
            "resource_status": status[:30],
        },
    )

    # Trim to most recent MAX_RECENT
    ids_to_keep = list(
        RecentAccess.objects.filter(user=user)
        .order_by("-accessed_at")
        .values_list("id", flat=True)[:MAX_RECENT]
    )
    RecentAccess.objects.filter(user=user).exclude(id__in=ids_to_keep).delete()


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def get_or_create_profile(user):
    """Get or create a UserProfile, auto-detecting user_type for new profiles."""
    try:
        return UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        if user.has_usable_password():
            user_type = "human"
        else:
            user_type = "agent"
        return UserProfile.objects.create(user=user, user_type=user_type)


def create_service_account(name):
    """Create a service account user with token and profile. Returns (user, token)."""
    user = User.objects.create_user(username=name)
    token = Token.objects.create(user=user)
    UserProfile.objects.create(user=user, user_type="service")
    return user, token


# ---------------------------------------------------------------------------
# Lock services
# ---------------------------------------------------------------------------


class LockConflict(Exception):
    """Raised when a lock is held by another user."""

    def __init__(self, lock):
        self.lock = lock
        super().__init__(f"Locked by {lock.user.username}")


def acquire_lock(user, project_id, role, session_id=""):
    """Acquire a lock, reconnect if same user, raise LockConflict if held by another."""
    try:
        existing = AgentLock.objects.get(project_id=project_id, role=role)
        if existing.user == user:
            if session_id:
                existing.session_id = session_id
                existing.save(update_fields=["session_id", "last_activity"])
            return existing
        raise LockConflict(existing)
    except AgentLock.DoesNotExist:
        return AgentLock.objects.create(
            project_id=project_id,
            role=role,
            user=user,
            session_id=session_id,
        )


def release_lock(lock_id, user, force=False):
    """Release a lock. If force=True, staff can release any lock."""
    lock = AgentLock.objects.get(pk=lock_id)
    if lock.user != user and not (force and user.is_staff):
        raise PermissionError("Only the lock owner or staff can release this lock.")
    lock.delete()


def list_locks(project_id=None):
    """List locks, optionally filtered by project."""
    qs = AgentLock.objects.select_related("user").all()
    if project_id:
        qs = qs.filter(project_id=project_id)
    return list(qs)


# ---------------------------------------------------------------------------
# Channel mapping services
# ---------------------------------------------------------------------------


def create_channel_mapping(provider, channel_id, project_id, channel_name=""):
    """Create a mapping. Returns the ChannelProjectMapping instance."""
    return ChannelProjectMapping.objects.create(
        provider=provider,
        channel_id=channel_id,
        project_id=project_id,
        channel_name=channel_name,
    )


def resolve_channel(provider, channel_id):
    """Look up the project_id for a channel. Returns project_id or None."""
    try:
        mapping = ChannelProjectMapping.objects.get(provider=provider, channel_id=channel_id)
        return mapping.project_id
    except ChannelProjectMapping.DoesNotExist:
        return None


def list_channel_mappings(provider=None, channel_id=None):
    """List mappings with optional filters."""
    qs = ChannelProjectMapping.objects.all()
    if provider:
        qs = qs.filter(provider=provider)
    if channel_id:
        qs = qs.filter(channel_id=channel_id)
    return list(qs)


def delete_channel_mapping(mapping_id):
    """Delete a mapping by ID. Raises DoesNotExist."""
    mapping = ChannelProjectMapping.objects.get(pk=mapping_id)
    mapping.delete()


# ---------------------------------------------------------------------------
# Identity services
# ---------------------------------------------------------------------------


def link_identity(user, provider, external_id, workspace_id=""):
    """Link an external identity to a user. Returns ExternalIdentity instance."""
    return ExternalIdentity.objects.create(
        user=user,
        provider=provider,
        external_id=external_id,
        workspace_id=workspace_id,
    )


def list_identities(user, provider=None):
    """List a user's external identities, optionally filtered by provider."""
    qs = ExternalIdentity.objects.filter(user=user)
    if provider:
        qs = qs.filter(provider=provider)
    return list(qs)


def unlink_identity(identity_id, user):
    """Remove a linked identity. Raises DoesNotExist if not found or not owned."""
    identity = ExternalIdentity.objects.get(pk=identity_id, user=user)
    identity.delete()


# ---------------------------------------------------------------------------
# Membership services
# ---------------------------------------------------------------------------


def add_member(project_id, user_id, role="member"):
    """Add a user to a project. Returns ProjectMembership instance."""
    user = User.objects.get(pk=user_id)
    return ProjectMembership.objects.create(
        user=user,
        project_id=project_id,
        role=role,
    )


def list_members(project_id):
    """List all members of a project with their roles."""
    return list(
        ProjectMembership.objects.select_related("user")
        .filter(project_id=project_id)
    )


def update_member_role(membership_id, role):
    """Change a member's role. Returns updated ProjectMembership."""
    membership = ProjectMembership.objects.get(pk=membership_id)
    membership.role = role
    membership.save(update_fields=["role"])
    return membership


def remove_member(membership_id):
    """Remove a member. Raises DoesNotExist."""
    membership = ProjectMembership.objects.get(pk=membership_id)
    membership.delete()


def check_membership(user, project_id):
    """Check if user has membership. Returns (has_access, role) tuple.
    Staff always returns (True, 'staff')."""
    if user.is_staff:
        return (True, "staff")
    try:
        membership = ProjectMembership.objects.get(user=user, project_id=project_id)
        return (True, membership.role)
    except ProjectMembership.DoesNotExist:
        return (False, None)


# ---------------------------------------------------------------------------
# User services
# ---------------------------------------------------------------------------


def list_users(search=None, user_type=None) -> QuerySet:
    """List users with their profiles. Supports search and type filter."""
    qs = User.objects.select_related("profile").all()
    if search:
        qs = qs.filter(username__icontains=search)
    if user_type:
        qs = qs.filter(profile__user_type=user_type)
    return list(qs.order_by("username"))


def get_user_detail(user_id):
    """Get a user with profile and memberships."""
    return User.objects.select_related("profile").prefetch_related(
        "project_memberships"
    ).get(pk=user_id)


def update_user_type(user_id, user_type):
    """Change a user's type. Raises ValueError for invalid type."""
    if user_type not in VALID_USER_TYPES:
        raise ValueError(f"Invalid user_type: {user_type}. Must be one of: {VALID_USER_TYPES}")
    user = User.objects.get(pk=user_id)
    profile = get_or_create_profile(user)
    profile.user_type = user_type
    profile.save(update_fields=["user_type"])
    return profile
