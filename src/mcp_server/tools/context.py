"""
MCP tool: vtf_get_context

Project-scoped overview for the architect — replaces the 3-call discovery
pattern (board_overview + list_workplans + search_tasks).
"""

import json

from mcp_server.project_context import get_default_project
from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from tasks.services import get_board_summary
from workplans.models import Workplan


@mcp.tool()
def vtf_get_context(project_id: str = "") -> str:
    """Get the current project context: workplans, task counts, what needs attention.

    Returns a structured overview scoped to the architect's project.
    Use this as the first call to understand the project state.
    If project_id is omitted, uses the session's default project.
    """
    pid = project_id or get_default_project()
    if not pid:
        return json.dumps(error_response(
            message="No project context available. Provide project_id or ensure X-VTF-Project header is set.",
            available_actions=["vtf_board_overview", "vtf_search_tasks"],
        ))

    # Board summary scoped to project
    summary = get_board_summary(project_id=pid)

    # Workplans for this project
    workplans = list(
        Workplan.objects.filter(project_id=pid)
        .values("id", "name", "status", "description")
        .order_by("-created_at")[:20]
    )

    data = {
        "project_id": pid,
        "counts": summary.get("counts", {}),
        "attention_items": summary.get("attention_items", []),
        "pending_reviews": summary.get("pending_reviews", []),
        "active_agents": summary.get("active_agents", []),
        "workplans": workplans,
    }

    total = sum(summary.get("counts", {}).values())
    done = summary.get("counts", {}).get("done", 0)
    attention = len(summary.get("attention_items", []))

    message = f"Project has {total} tasks ({done} done"
    if attention:
        message += f", {attention} need attention"
    message += f"), {len(workplans)} workplan(s)."

    return json.dumps(success_response(
        data=data,
        message=message,
        available_actions=["vtf_plan_work", "vtf_task_detail", "vtf_search_tasks"],
    ))
