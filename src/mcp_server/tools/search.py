"""
MCP tool: vtf_search_tasks

Finds tasks by criteria with enriched results. Supports filtering by
status, project, workplan, milestone, labels, assigned_to, and text query.
Returns paginated results with available_actions per task.
"""
import json

from django.db.models import Q

from mcp_server.responses import success_response
from mcp_server.server import mcp
from tasks.models import Task
from tasks.services import get_available_actions


@mcp.tool()
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
) -> str:
    """Search for tasks matching specific criteria.

    Returns enriched results with status context and available actions for
    each task. Use filters to narrow results.
    """
    # Convert empty strings to None for clarity
    status_filter = status or None
    project_id_filter = project_id or None
    workplan_id_filter = workplan_id or None
    milestone_id_filter = milestone_id or None
    assigned_to_filter = assigned_to or None
    query_filter = query or None

    # Clamp limit to 1-100
    limit = max(1, min(100, limit))
    offset = max(0, offset)

    # Build queryset with filters
    qs = Task.objects.select_related("project", "workplan", "milestone").all()

    if status_filter:
        qs = qs.filter(status=status_filter)

    if project_id_filter:
        qs = qs.filter(project_id=project_id_filter)

    if workplan_id_filter:
        qs = qs.filter(workplan_id=workplan_id_filter)

    if milestone_id_filter:
        qs = qs.filter(milestone_id=milestone_id_filter)

    if assigned_to_filter:
        qs = qs.filter(assigned_to=assigned_to_filter)

    if labels:
        label_list = [l.strip() for l in labels.split(",") if l.strip()]
        for label in label_list:
            qs = qs.filter(labels__contains=label)

    if query_filter:
        qs = qs.filter(
            Q(title__icontains=query_filter) | Q(description__icontains=query_filter)
        )

    # Get total count before pagination
    total_count = qs.count()

    # Apply pagination
    tasks_page = qs[offset: offset + limit]

    # Build enriched task list
    task_list = []
    for task in tasks_page:
        task_dict = {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "milestone": task.milestone.name if task.milestone else None,
            "claimed_by": task.claimed_by,
            "labels": task.labels,
            "has_spec": bool(task.spec),
            "judge": task.judge,
            "available_actions": get_available_actions(task),
        }
        task_list.append(task_dict)

    has_more = (offset + limit) < total_count

    # Build summary message
    end_idx = min(offset + limit, total_count)
    if total_count == 0:
        message = "No tasks found matching filters."
    else:
        message = f"Found {total_count} task{'s' if total_count != 1 else ''} matching filters. Showing {offset + 1}-{end_idx}."

    data = {
        "tasks": task_list,
        "total_count": total_count,
        "has_more": has_more,
        "offset": offset,
        "limit": limit,
    }

    next_actions = ["vtf_task_detail"]
    if has_more:
        next_actions.append(f"vtf_search_tasks(offset={offset + limit})")

    return json.dumps(
        success_response(
            data=data,
            message=message,
            available_actions=next_actions,
        )
    )
