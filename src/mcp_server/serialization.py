"""Entity serialization helpers for MCP tools.

Uses v2 DRF serializers as the single source of truth for entity
response shapes. MCP tools call these helpers instead of building
dicts manually.
"""
from django.contrib.auth.models import AnonymousUser


def _make_request_context():
    """Build a minimal request context for v2 serializers.

    V2 serializers need request.user for permissions computation.
    MCP tools run server-side with staff access, so we use a
    synthetic context.
    """
    from mcp_server.user_context import get_current_user

    class _FakeRequest:
        def __init__(self, user):
            self.user = user or AnonymousUser()
            self.version = "v2"

    user = get_current_user()
    return {"request": _FakeRequest(user)}


def serialize_task(task) -> dict:
    """Serialize a Task instance using TaskV2Serializer."""
    from tasks.serializers_v2 import TaskV2Serializer
    ctx = _make_request_context()
    return TaskV2Serializer(task, context=ctx).data


def serialize_task_detail(task, expand=None) -> dict:
    """Serialize a Task with optional expand support."""
    from tasks.serializers_v2 import TaskDetailV2Serializer
    ctx = _make_request_context()
    if expand:
        ctx["expand"] = expand
    return TaskDetailV2Serializer(task, context=ctx).data


def serialize_project(project) -> dict:
    """Serialize a Project instance using ProjectV2Serializer."""
    from projects.serializers_v2 import ProjectV2Serializer
    ctx = _make_request_context()
    return ProjectV2Serializer(project, context=ctx).data


def serialize_workplan(workplan) -> dict:
    """Serialize a Workplan instance using WorkplanV2Serializer."""
    from workplans.serializers_v2 import WorkplanV2Serializer
    ctx = _make_request_context()
    return WorkplanV2Serializer(workplan, context=ctx).data


def serialize_milestone(milestone) -> dict:
    """Serialize a Milestone instance using MilestoneV2Serializer."""
    from workplans.serializers_v2 import MilestoneV2Serializer
    ctx = _make_request_context()
    return MilestoneV2Serializer(milestone, context=ctx).data


# --- Non-entity serializers (admin/utility data) ---
# These don't have DRF v2 serializers but still use structured helpers
# to avoid manual dict construction in tools.

def serialize_lock(lock) -> dict:
    """Serialize an AgentLock instance."""
    from core.refs import ActorRefField
    actor = ActorRefField()
    return {
        "id": lock.pk,
        "project_id": lock.project_id,
        "role": lock.role,
        "user": actor.to_representation(lock.user),
        "created_at": lock.created_at.isoformat(),
        "last_activity": lock.last_activity.isoformat() if lock.last_activity else None,
    }


def serialize_channel_mapping(mapping) -> dict:
    """Serialize a ChannelProjectMapping instance."""
    return {
        "id": mapping.pk,
        "provider": mapping.provider,
        "channel_id": mapping.channel_id,
        "channel_name": mapping.channel_name,
        "project_id": mapping.project_id,
    }


def serialize_member(membership) -> dict:
    """Serialize a ProjectMembership instance."""
    from core.refs import ActorRefField
    actor = ActorRefField()
    return {
        "user": actor.to_representation(membership.user),
        "role": membership.role,
    }


def serialize_note(note) -> dict:
    """Serialize a Note instance."""
    from core.refs import ActorRefField
    actor = ActorRefField()
    return {
        "id": str(note.id),
        "text": note.text,
        "actor": actor.to_representation(note.actor) if note.actor else None,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


def serialize_user_identity(user) -> dict:
    """Serialize user identity for vtf_whoami."""
    from core.refs import ProjectRefSerializer
    from prefs.models import ProjectMembership
    from prefs.services import get_or_create_profile
    from projects.models import Project

    profile = get_or_create_profile(user)
    memberships = ProjectMembership.objects.filter(user=user)

    project_ids = [m.project_id for m in memberships]
    projects_qs = Project.objects.filter(pk__in=project_ids)
    project_map = {p.id: ProjectRefSerializer(p).data for p in projects_qs}

    return {
        "user_id": user.pk,
        "username": user.username,
        "user_type": profile.user_type,
        "is_staff": user.is_staff,
        "projects": [
            {"project": project_map.get(m.project_id, {"id": m.project_id, "name": None}), "role": m.role}
            for m in memberships
        ],
    }
