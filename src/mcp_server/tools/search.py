"""MCP tool: vtf_search_tasks — search with v2 serialized results."""
from django.db.models import Q

from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.parsers import parse_csv_list
from mcp_server.serialization import serialize_task
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_search_tasks(
    status: str = "",
    project_id: str = "",
    workplan_id: str = "",
    milestone_id: str = "",
    labels: str = "",
    assigned_to: str = "",
    query: str = "",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Search for tasks matching specific criteria.

    Returns v2-serialized results with embedded refs and permissions.
    """
    from tasks.models import Task

    limit = max(1, min(100, limit))
    offset = max(0, offset)

    qs = Task.objects.select_related(
        "project", "workplan", "milestone", "assigned_to", "claimed_by", "created_by",
    ).all()

    if status:
        qs = qs.filter(status=status)
    if project_id:
        qs = qs.filter(project_id=project_id)
    if workplan_id:
        qs = qs.filter(workplan_id=workplan_id)
    if milestone_id:
        qs = qs.filter(milestone_id=milestone_id)
    if assigned_to:
        qs = qs.filter(assigned_to__username=assigned_to)
    if labels:
        for label in parse_csv_list(labels):
            qs = qs.filter(labels__contains=label)
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))

    total_count = qs.count()
    tasks_page = qs[offset:offset + limit]

    task_list = [serialize_task(task) for task in tasks_page]

    has_more = (offset + limit) < total_count
    end_idx = min(offset + limit, total_count)

    if total_count == 0:
        message = "No tasks found matching filters."
    else:
        message = f"Found {total_count} task{'s' if total_count != 1 else ''}. Showing {offset + 1}-{end_idx}."

    available_actions = ["vtf_task_detail"]
    if has_more:
        available_actions.append(f"vtf_search_tasks(offset={offset + limit})")

    return {
        "data": {"tasks": task_list, "total_count": total_count, "has_more": has_more, "offset": offset, "limit": limit},
        "message": message,
        "available_actions": available_actions,
    }
