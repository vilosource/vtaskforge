"""MCP tool: vtf_get_context — project overview with v2 serialized data."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.project_context import get_default_project
from mcp_server.serialization import serialize_workplan
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_get_context(project_id: str = "") -> dict:
    """Get the current project context: workplans, task counts, what needs attention.

    Returns a structured overview scoped to the architect's project.
    If project_id is omitted, uses the session's default project.
    """
    from tasks.services import get_board_summary
    from workplans.models import Workplan

    pid = project_id or get_default_project()
    if not pid:
        return {"error": True, "message": "No project context. Provide project_id or set X-VTF-Project header."}

    summary = get_board_summary(project_id=pid)

    workplans = Workplan.objects.select_related("project", "owner", "created_by").filter(
        project_id=pid
    ).order_by("-created_at")[:20]
    workplan_data = [serialize_workplan(wp) for wp in workplans]

    total = sum(summary.get("counts", {}).values())
    done = summary.get("counts", {}).get("done", 0)
    attention = len(summary.get("attention_items", []))

    message = f"Project has {total} tasks ({done} done"
    if attention:
        message += f", {attention} need attention"
    message += f"), {len(workplan_data)} workplan(s)."

    return {
        "data": {
            "project_id": pid,
            "counts": summary.get("counts", {}),
            "attention_items": summary.get("attention_items", []),
            "pending_reviews": summary.get("pending_reviews", []),
            "active_agents": summary.get("active_agents", []),
            "workplans": workplan_data,
        },
        "message": message,
        "available_actions": ["vtf_plan_work", "vtf_task_detail", "vtf_search_tasks"],
    }
