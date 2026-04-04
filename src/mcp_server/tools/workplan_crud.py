"""MCP tools: workplan CRUD — create, list, update, archive, complete."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.parsers import parse_csv_list
from mcp_server.serialization import serialize_workplan
from mcp_server.server import mcp
from mcp_server.project_context import get_default_project


@mcp.tool()
@handle_errors
@serialize_response
def vtf_create_workplan(name: str, project_id: str = "", description: str = "", tags: str = "") -> dict:
    """Create a new workplan."""
    from projects.models import Project
    from workplans.models import Workplan
    from mcp_server.user_context import get_current_user

    if not name:
        return {"error": True, "message": "'name' is required."}

    pid = project_id or get_default_project()
    if not pid:
        return {"error": True, "message": "'project_id' is required."}

    try:
        project = Project.objects.get(pk=pid)
    except Project.DoesNotExist:
        return {"error": True, "message": f"Project '{pid}' not found."}

    user = get_current_user()
    wp = Workplan.objects.create(
        name=name, project=project, description=description,
        tags=parse_csv_list(tags) if tags else [],
        owner=user, created_by=user,
    )
    return {
        "data": {"workplan": serialize_workplan(wp)},
        "message": f"Created workplan '{wp.name}' ({wp.id}).",
        "available_actions": ["vtf_create_milestone", "vtf_create_task"],
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_list_workplans(project_id: str = "", status: str = "") -> dict:
    """List workplans, optionally filtered by project and status."""
    from workplans.models import Workplan

    pid = project_id or get_default_project()
    qs = Workplan.objects.select_related("project", "owner", "created_by").all()
    if pid:
        qs = qs.filter(project_id=pid)
    if status:
        qs = qs.filter(status=status)

    workplans = [serialize_workplan(wp) for wp in qs[:50]]
    return {
        "data": {"workplans": workplans, "count": len(workplans)},
        "message": f"Found {len(workplans)} workplan(s).",
        "available_actions": ["vtf_create_workplan", "vtf_workplan_tree"],
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_archive_workplan(workplan_id: str) -> dict:
    """Archive a workplan."""
    from workplans.models import Workplan

    wp = Workplan.objects.select_related("project", "owner", "created_by").get(pk=workplan_id)
    wp.status = "archived"
    wp.save(update_fields=["status", "updated_at"])
    return {
        "data": {"workplan": serialize_workplan(wp)},
        "message": f"Archived workplan '{wp.name}'.",
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_complete_workplan(workplan_id: str) -> dict:
    """Complete a workplan."""
    from workplans.models import Workplan

    wp = Workplan.objects.select_related("project", "owner", "created_by").get(pk=workplan_id)
    wp.status = "completed"
    wp.save(update_fields=["status", "updated_at"])
    return {
        "data": {"workplan": serialize_workplan(wp)},
        "message": f"Completed workplan '{wp.name}'.",
    }
