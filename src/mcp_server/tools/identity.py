"""MCP tools for user management and identity.

vtf_whoami — current user identity and memberships
vtf_manage_lock — acquire/release/list agent session locks
vtf_resolve_channel — resolve external channel to project
vtf_list_members — list project members
vtf_manage_channel_mapping — CRUD for channel-to-project mappings
"""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.project_context import get_default_project
from mcp_server.serialization import (
    serialize_channel_mapping,
    serialize_lock,
    serialize_member,
    serialize_user_identity,
)
from mcp_server.server import mcp
from mcp_server.user_context import get_current_user

from prefs.models import ChannelProjectMapping
from prefs.services import (
    LockConflict,
    acquire_lock,
    create_channel_mapping,
    delete_channel_mapping,
    list_channel_mappings,
    list_locks,
    list_members,
    release_lock,
    resolve_channel,
)


@mcp.tool()
@handle_errors
@serialize_response
def vtf_whoami() -> dict:
    """Return the current user's identity: username, user type, staff status, and project memberships."""
    user = get_current_user()
    if not user:
        return {"error": True, "message": "No user context available. Ensure authentication is configured."}

    data = serialize_user_identity(user)
    return {
        "data": data,
        "message": f"Authenticated as {data['username']} ({data['user_type']}), {len(data['projects'])} project(s).",
        "available_actions": ["vtf_get_context", "vtf_manage_lock"],
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_manage_lock(action: str, project_id: str = "", role: str = "", lock_id: int = 0) -> dict:
    """Manage agent session locks. Actions: list, acquire, release."""
    user = get_current_user()

    if action == "list":
        locks = list_locks(project_id=project_id or None)
        lock_data = [serialize_lock(lock) for lock in locks]
        return {"data": {"locks": lock_data}, "message": f"{len(lock_data)} active lock(s)."}

    elif action == "acquire":
        if not project_id or not role:
            return {"error": True, "message": "project_id and role are required to acquire a lock."}
        if not user:
            return {"error": True, "message": "No user context — cannot acquire lock."}
        try:
            lock = acquire_lock(user, project_id, role)
            return {"data": serialize_lock(lock), "message": f"Lock acquired: {role}@{project_id}."}
        except LockConflict as e:
            return {"error": True, "message": f"Lock conflict: {role}@{project_id} is held by {e.lock.user.username}."}

    elif action == "release":
        if not lock_id:
            return {"error": True, "message": "lock_id is required to release a lock."}
        if not user:
            return {"error": True, "message": "No user context — cannot release lock."}
        try:
            release_lock(lock_id, user)
            return {"data": {"released": lock_id}, "message": f"Lock {lock_id} released."}
        except Exception:
            return {"error": True, "message": f"Lock {lock_id} not found or not owned by you."}

    return {"error": True, "message": f"Unknown action '{action}'. Use: list, acquire, release."}


@mcp.tool()
@handle_errors
@serialize_response
def vtf_resolve_channel(provider: str, channel_id: str) -> dict:
    """Resolve an external channel to a vtf project."""
    pid = resolve_channel(provider, channel_id)
    if pid:
        return {"data": {"project_id": pid, "provider": provider, "channel_id": channel_id},
                "message": f"Channel {provider}:{channel_id} maps to project '{pid}'."}
    return {"error": True, "message": f"No mapping found for {provider}:{channel_id}."}


@mcp.tool()
@handle_errors
@serialize_response
def vtf_list_members(project_id: str = "") -> dict:
    """List members of a project with their roles."""
    pid = project_id or get_default_project()
    if not pid:
        return {"error": True, "message": "No project context. Provide project_id or set X-VTF-Project header."}

    members = list_members(pid)
    member_data = [serialize_member(m) for m in members]

    return {
        "data": {"project_id": pid, "members": member_data},
        "message": f"Project '{pid}' has {len(member_data)} member(s).",
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_manage_channel_mapping(action: str, provider: str = "", channel_id: str = "",
                                channel_name: str = "", project_id: str = "", mapping_id: int = 0) -> dict:
    """Manage channel-to-project mappings. Actions: list, create, delete."""
    if action == "list":
        mappings = list_channel_mappings(provider=provider or None)
        mapping_data = [serialize_channel_mapping(m) for m in mappings]
        return {"data": {"mappings": mapping_data}, "message": f"{len(mapping_data)} mapping(s)."}

    elif action == "create":
        if not provider or not channel_id or not project_id:
            return {"error": True, "message": "provider, channel_id, and project_id are required."}
        mapping = create_channel_mapping(provider, channel_id, project_id, channel_name)
        return {"data": serialize_channel_mapping(mapping),
                "message": f"Mapping created: {provider}:{channel_id} → {project_id}."}

    elif action == "delete":
        if not mapping_id:
            return {"error": True, "message": "mapping_id is required to delete a mapping."}
        try:
            delete_channel_mapping(mapping_id)
            return {"data": {"deleted": mapping_id}, "message": f"Mapping {mapping_id} deleted."}
        except ChannelProjectMapping.DoesNotExist:
            return {"error": True, "message": f"Mapping {mapping_id} not found."}

    return {"error": True, "message": f"Unknown action '{action}'. Use: list, create, delete."}
