"""
MCP tool: vtf_workplan_tree

Read-only hierarchical view: workplan → milestones → task summaries.
Composes from ORM queries since no existing endpoint returns this in one call.
"""
import json

from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp


@mcp.tool()
def vtf_workplan_tree(workplan_id: str) -> str:
    """Get hierarchical view of a workplan: milestones and their tasks.

    Returns the complete structure of a workplan including all milestones
    (ordered by sort order) and task summaries within each milestone.
    Also shows tasks assigned to the workplan but not in any milestone.
    """
    from tasks.models import Task
    from workplans.models import Workplan

    try:
        wp = Workplan.objects.get(pk=workplan_id)
    except Workplan.DoesNotExist:
        return json.dumps(
            error_response(
                message=f"Workplan '{workplan_id}' not found.",
                data={"workplan_id": workplan_id},
                available_actions=["vtf_manage_workplan(action=list)"],
            )
        )

    milestones = wp.milestones.order_by("order", "created_at")
    result_milestones = []
    for ms in milestones:
        tasks = list(
            ms.tasks.all().values_list("id", "title", "status", "labels")
        )
        result_milestones.append(
            {
                "id": ms.id,
                "name": ms.name,
                "status": ms.status,
                "order": ms.order,
                "tasks": [
                    {"id": t[0], "title": t[1], "status": t[2], "labels": t[3]}
                    for t in tasks
                ],
            }
        )

    unassigned = list(
        Task.objects.filter(workplan=wp, milestone__isnull=True).values_list(
            "id", "title", "status", "labels"
        )
    )
    unassigned_tasks = [
        {"id": t[0], "title": t[1], "status": t[2], "labels": t[3]}
        for t in unassigned
    ]

    return json.dumps(
        success_response(
            data={
                "workplan": {
                    "id": wp.id,
                    "name": wp.name,
                    "status": wp.status,
                },
                "milestones": result_milestones,
                "unassigned_tasks": unassigned_tasks,
            },
            message=f"Workplan '{wp.name}' tree: {len(result_milestones)} milestone(s), {len(unassigned_tasks)} unassigned task(s).",
            available_actions=[
                "vtf_manage_workplan(action=list)",
                "vtf_task_detail",
            ],
        )
    )
