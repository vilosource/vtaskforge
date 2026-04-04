"""MCP tools: milestone CRUD — create, list, activate, complete, delete."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.serialization import serialize_milestone
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_create_milestone(workplan_id: str, name: str, description: str = "", order: int = 0) -> dict:
    """Create a new milestone in a workplan."""
    from workplans.models import Milestone, Workplan
    from mcp_server.user_context import get_current_user

    if not workplan_id or not name:
        return {"error": True, "message": "'workplan_id' and 'name' are required."}

    try:
        workplan = Workplan.objects.get(pk=workplan_id)
    except Workplan.DoesNotExist:
        return {"error": True, "message": f"Workplan '{workplan_id}' not found."}

    user = get_current_user()
    ms = Milestone.objects.create(
        workplan=workplan, name=name, description=description,
        order=order, created_by=user,
    )
    return {
        "data": {"milestone": serialize_milestone(ms)},
        "message": f"Created milestone '{ms.name}' ({ms.id}).",
        "available_actions": ["vtf_create_task", "vtf_list_milestones"],
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_list_milestones(workplan_id: str) -> dict:
    """List milestones in a workplan."""
    from workplans.models import Milestone

    if not workplan_id:
        return {"error": True, "message": "'workplan_id' is required."}

    milestones = Milestone.objects.select_related("workplan", "created_by").filter(
        workplan_id=workplan_id
    ).order_by("order")

    data = [serialize_milestone(ms) for ms in milestones]
    return {
        "data": {"milestones": data, "count": len(data)},
        "message": f"Found {len(data)} milestone(s).",
        "available_actions": ["vtf_create_milestone", "vtf_workplan_tree"],
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_activate_milestone(milestone_id: str) -> dict:
    """Activate a pending milestone."""
    from workplans.models import Milestone

    ms = Milestone.objects.select_related("workplan", "created_by").get(pk=milestone_id)
    if ms.status != "pending":
        return {"error": True, "message": f"Milestone is '{ms.status}', not 'pending'."}

    ms.status = "active"
    ms.save(update_fields=["status", "updated_at"])
    return {
        "data": {"milestone": serialize_milestone(ms)},
        "message": f"Activated milestone '{ms.name}'.",
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_complete_milestone(milestone_id: str) -> dict:
    """Complete an active milestone."""
    from workplans.models import Milestone

    ms = Milestone.objects.select_related("workplan", "created_by").get(pk=milestone_id)
    if ms.status != "active":
        return {"error": True, "message": f"Milestone is '{ms.status}', not 'active'."}

    ms.status = "completed"
    ms.save(update_fields=["status", "updated_at"])
    return {
        "data": {"milestone": serialize_milestone(ms)},
        "message": f"Completed milestone '{ms.name}'.",
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_delete_milestone(milestone_id: str) -> dict:
    """Delete a milestone."""
    from workplans.models import Milestone

    ms = Milestone.objects.get(pk=milestone_id)
    name = ms.name
    ms.delete()
    return {
        "data": {},
        "message": f"Deleted milestone '{name}' ({milestone_id}).",
    }
