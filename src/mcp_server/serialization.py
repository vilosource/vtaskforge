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
