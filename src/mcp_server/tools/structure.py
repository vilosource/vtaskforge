"""MCP tool: vtf_workplan_tree — hierarchical view with v2 serialized data."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.serialization import serialize_milestone, serialize_task, serialize_workplan
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_workplan_tree(workplan_id: str) -> dict:
    """Get hierarchical view of a workplan: milestones and their tasks.

    Returns the complete structure with v2-serialized entities.
    """
    from tasks.models import Task
    from workplans.models import Workplan

    wp = Workplan.objects.select_related("project", "owner", "created_by").get(pk=workplan_id)

    milestones = wp.milestones.select_related("workplan", "created_by").order_by("order", "created_at")
    result_milestones = []
    for ms in milestones:
        tasks = Task.objects.select_related(
            "project", "workplan", "milestone", "assigned_to", "claimed_by", "created_by",
        ).filter(milestone=ms)
        result_milestones.append({
            "milestone": serialize_milestone(ms),
            "tasks": [serialize_task(t) for t in tasks],
        })

    unassigned = Task.objects.select_related(
        "project", "workplan", "milestone", "assigned_to", "claimed_by", "created_by",
    ).filter(workplan=wp, milestone__isnull=True)

    return {
        "data": {
            "workplan": serialize_workplan(wp),
            "milestones": result_milestones,
            "unassigned_tasks": [serialize_task(t) for t in unassigned],
        },
        "message": f"Workplan '{wp.name}': {len(result_milestones)} milestone(s), {len(unassigned)} unassigned task(s).",
        "available_actions": ["vtf_list_workplans", "vtf_task_detail"],
    }
