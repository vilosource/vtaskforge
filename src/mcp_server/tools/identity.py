"""
MCP tools for user management and identity.

vtf_whoami — current user identity and memberships
vtf_manage_lock — acquire/release/list agent session locks
vtf_resolve_channel — resolve external channel to project
vtf_list_members — list project members
vtf_manage_channel_mapping — CRUD for channel-to-project mappings
"""

import json

from mcp_server.project_context import get_default_project
from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from mcp_server.user_context import get_current_user

from prefs.models import ChannelProjectMapping, ProjectMembership
from prefs.services import (
    LockConflict,
    acquire_lock,
    create_channel_mapping,
    delete_channel_mapping,
    get_or_create_profile,
    list_channel_mappings,
    list_locks,
    list_members,
    release_lock,
    resolve_channel,
)


@mcp.tool()
def vtf_whoami() -> str:
    """Return the current user's identity: username, user type, staff status, and project memberships.

    Use this to understand who you are and what projects you have access to.
    """
    user = get_current_user()
    if not user:
        return json.dumps(error_response(
            message="No user context available. Ensure authentication is configured.",
            available_actions=["vtf_get_context"],
        ))

    profile = get_or_create_profile(user)
    memberships = ProjectMembership.objects.filter(user=user)
    projects = [
        {"project_id": m.project_id, "role": m.role}
        for m in memberships
    ]

    data = {
        "user_id": user.pk,
        "username": user.username,
        "user_type": profile.user_type,
        "is_staff": user.is_staff,
        "projects": projects,
    }

    return json.dumps(success_response(
        data=data,
        message=f"Authenticated as {user.username} ({profile.user_type}), {len(projects)} project(s).",
        available_actions=["vtf_get_context", "vtf_manage_lock"],
    ))


@mcp.tool()
def vtf_manage_lock(
    action: str,
    project_id: str = "",
    role: str = "",
    lock_id: int = 0,
) -> str:
    """Manage agent session locks.

    Actions:
      - list: List all active locks (optionally filter by project_id)
      - acquire: Acquire a lock for a project+role (reconnects if already held by you)
      - release: Release a lock by lock_id

    Locks prevent duplicate agent sessions. Acquire a lock before starting work
    on a project in a specific role (e.g., architect, executor).
    """
    user = get_current_user()

    if action == "list":
        locks = list_locks(project_id=project_id or None)
        lock_data = [
            {
                "id": lock.pk,
                "project_id": lock.project_id,
                "role": lock.role,
                "user": lock.user.username,
                "created_at": lock.created_at.isoformat(),
                "last_activity": lock.last_activity.isoformat(),
            }
            for lock in locks
        ]
        return json.dumps(success_response(
            data={"locks": lock_data},
            message=f"{len(lock_data)} active lock(s).",
            available_actions=["vtf_manage_lock"],
        ))

    elif action == "acquire":
        if not project_id or not role:
            return json.dumps(error_response(
                message="project_id and role are required to acquire a lock.",
                available_actions=["vtf_manage_lock"],
            ))
        if not user:
            return json.dumps(error_response(
                message="No user context — cannot acquire lock.",
            ))
        try:
            lock = acquire_lock(user, project_id, role)
            return json.dumps(success_response(
                data={
                    "id": lock.pk,
                    "project_id": lock.project_id,
                    "role": lock.role,
                    "user": lock.user.username,
                },
                message=f"Lock acquired: {role}@{project_id}.",
                available_actions=["vtf_get_context", "vtf_manage_lock"],
            ))
        except LockConflict as e:
            return json.dumps(error_response(
                message=f"Lock conflict: {role}@{project_id} is held by {e.lock.user.username}.",
                data={"locked_by": e.lock.user.username, "since": e.lock.created_at.isoformat()},
                available_actions=["vtf_manage_lock"],
            ))

    elif action == "release":
        if not lock_id:
            return json.dumps(error_response(
                message="lock_id is required to release a lock.",
                available_actions=["vtf_manage_lock"],
            ))
        if not user:
            return json.dumps(error_response(
                message="No user context — cannot release lock.",
            ))
        try:
            release_lock(lock_id, user)
            return json.dumps(success_response(
                data={"released": lock_id},
                message=f"Lock {lock_id} released.",
                available_actions=["vtf_manage_lock"],
            ))
        except Exception:
            return json.dumps(error_response(
                message=f"Lock {lock_id} not found or not owned by you.",
                available_actions=["vtf_manage_lock"],
            ))

    else:
        return json.dumps(error_response(
            message=f"Unknown action '{action}'. Use: list, acquire, release.",
            available_actions=["vtf_manage_lock"],
        ))


@mcp.tool()
def vtf_resolve_channel(
    provider: str,
    channel_id: str,
) -> str:
    """Resolve an external channel (Slack, etc.) to a vtf project.

    Returns the project_id mapped to this channel, or an error if no mapping exists.
    Use this when you receive a message from an external channel and need to know
    which project context to use.
    """
    project_id = resolve_channel(provider, channel_id)
    if project_id:
        return json.dumps(success_response(
            data={"project_id": project_id, "provider": provider, "channel_id": channel_id},
            message=f"Channel {provider}:{channel_id} maps to project '{project_id}'.",
            available_actions=["vtf_get_context"],
        ))
    return json.dumps(error_response(
        message=f"No mapping found for {provider}:{channel_id}.",
        available_actions=["vtf_manage_channel_mapping"],
    ))


@mcp.tool()
def vtf_list_members(project_id: str = "") -> str:
    """List members of a project with their roles.

    If project_id is omitted, uses the session's default project.
    Returns usernames and roles (owner, member, viewer).
    """
    pid = project_id or get_default_project()
    if not pid:
        return json.dumps(error_response(
            message="No project context. Provide project_id or set X-VTF-Project header.",
            available_actions=["vtf_get_context"],
        ))

    members = list_members(pid)
    member_data = [
        {"user_id": m.user.pk, "username": m.user.username, "role": m.role}
        for m in members
    ]

    return json.dumps(success_response(
        data={"project_id": pid, "members": member_data},
        message=f"Project '{pid}' has {len(member_data)} member(s).",
        available_actions=["vtf_manage_lock", "vtf_get_context"],
    ))


@mcp.tool()
def vtf_manage_channel_mapping(
    action: str,
    provider: str = "",
    channel_id: str = "",
    channel_name: str = "",
    project_id: str = "",
    mapping_id: int = 0,
) -> str:
    """Manage channel-to-project mappings.

    Actions:
      - list: List all mappings (optionally filter by provider)
      - create: Create a new mapping (requires provider, channel_id, project_id)
      - delete: Remove a mapping by mapping_id
    """
    if action == "list":
        mappings = list_channel_mappings(provider=provider or None)
        mapping_data = [
            {
                "id": m.pk,
                "provider": m.provider,
                "channel_id": m.channel_id,
                "channel_name": m.channel_name,
                "project_id": m.project_id,
            }
            for m in mappings
        ]
        return json.dumps(success_response(
            data={"mappings": mapping_data},
            message=f"{len(mapping_data)} mapping(s).",
            available_actions=["vtf_manage_channel_mapping"],
        ))

    elif action == "create":
        if not provider or not channel_id or not project_id:
            return json.dumps(error_response(
                message="provider, channel_id, and project_id are required to create a mapping.",
                available_actions=["vtf_manage_channel_mapping"],
            ))
        mapping = create_channel_mapping(provider, channel_id, project_id, channel_name)
        return json.dumps(success_response(
            data={
                "id": mapping.pk,
                "provider": mapping.provider,
                "channel_id": mapping.channel_id,
                "project_id": mapping.project_id,
            },
            message=f"Mapping created: {provider}:{channel_id} → {project_id}.",
            available_actions=["vtf_manage_channel_mapping"],
        ))

    elif action == "delete":
        if not mapping_id:
            return json.dumps(error_response(
                message="mapping_id is required to delete a mapping.",
                available_actions=["vtf_manage_channel_mapping"],
            ))
        try:
            delete_channel_mapping(mapping_id)
            return json.dumps(success_response(
                data={"deleted": mapping_id},
                message=f"Mapping {mapping_id} deleted.",
                available_actions=["vtf_manage_channel_mapping"],
            ))
        except ChannelProjectMapping.DoesNotExist:
            return json.dumps(error_response(
                message=f"Mapping {mapping_id} not found.",
                available_actions=["vtf_manage_channel_mapping"],
            ))

    else:
        return json.dumps(error_response(
            message=f"Unknown action '{action}'. Use: list, create, delete.",
            available_actions=["vtf_manage_channel_mapping"],
        ))
