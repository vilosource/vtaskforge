"""MCP tool: vtf_create_link — create a Link between two entities.

Exposes the Link model via MCP for the same workflows the REST
LinkViewSet serves (see links/views.py). Primary use case: recording
task-to-task dependencies via link_type=depends_on so the claimable
filter gates downstream tasks until upstream is done.
"""
import json

from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.server import mcp


def _resolve_project(source_type: str, source_id: str):
    """Mirror LinkViewSet._resolve_project (links/views.py:54-70)."""
    if not source_type or not source_id:
        return None
    try:
        if source_type == "task":
            from tasks.models import Task
            return Task.objects.select_related("project").get(pk=source_id).project
        if source_type == "workplan":
            from workplans.models import Workplan
            return Workplan.objects.select_related("project").get(pk=source_id).project
        if source_type == "milestone":
            from workplans.models import Milestone
            return Milestone.objects.select_related("workplan__project").get(pk=source_id).workplan.project
    except Exception:
        return None
    return None


@mcp.tool()
@handle_errors
@serialize_response
def vtf_create_link(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    link_type: str,
    metadata: str = "",
) -> dict:
    """Create a link between two entities.

    The primary use case is task-to-task dependencies — pass
    source_type=task, target_type=task, link_type=depends_on. The source
    task will stay unclaimable until every depends_on target is `done`.

    Args:
        source_type: Entity type of the source. One of: task, workplan, milestone.
        source_id: Entity ID of the source.
        target_type: Entity type of the target. Typically task; free-form for
            doc/commit/file/jira targets.
        target_id: Entity ID of the target.
        link_type: Relationship type. One of: depends_on, blocks, relates_to,
            commit, mr, area, doc, file, jira.
        metadata: Optional JSON dict of extra fields (e.g. commit SHA).

    Returns:
        Created link fields including the generated link id.
    """
    from links.models import Link, LINK_TYPE_CHOICES, SOURCE_TYPE_CHOICES
    from links.serializers import LinkSerializer
    from mcp_server.user_context import get_current_user

    valid_source_types = {c[0] for c in SOURCE_TYPE_CHOICES}
    if source_type not in valid_source_types:
        return {
            "error": True,
            "message": f"Invalid source_type '{source_type}'. Must be one of: {', '.join(sorted(valid_source_types))}.",
        }

    valid_link_types = {c[0] for c in LINK_TYPE_CHOICES}
    if link_type not in valid_link_types:
        return {
            "error": True,
            "message": f"Invalid link_type '{link_type}'. Must be one of: {', '.join(sorted(valid_link_types))}.",
        }

    if not source_id or not target_id or not target_type:
        return {"error": True, "message": "source_id, target_type, and target_id are required."}

    metadata_value = None
    if metadata:
        try:
            parsed = json.loads(metadata)
        except json.JSONDecodeError as e:
            return {"error": True, "message": f"metadata must be valid JSON: {e}"}
        if not isinstance(parsed, dict):
            return {"error": True, "message": "metadata must be a JSON object."}
        metadata_value = parsed

    project = _resolve_project(source_type, source_id)
    if project is None:
        return {
            "error": True,
            "message": f"Source {source_type} '{source_id}' not found.",
        }

    user = get_current_user()
    link = Link.objects.create(
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        link_type=link_type,
        metadata=metadata_value,
        project=project,
        created_by=user if user else None,
    )

    return {
        "data": {"link": LinkSerializer(link).data},
        "message": (
            f"Created link {link.id}: {source_type}:{source_id} "
            f"--[{link_type}]--> {target_type}:{target_id}."
        ),
        "available_actions": ["vtf_task_detail"],
    }
