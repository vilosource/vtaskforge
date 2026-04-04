"""MCP tools: vtf_assign_task, vtf_unassign_task."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.serialization import serialize_task
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_assign_task(task_id: str, assigned_to: str) -> dict:
    """Assign a task to an agent or user.

    Args:
        task_id: Task to assign
        assigned_to: Username of agent/user to assign to
    """
    from django.contrib.auth.models import User
    from tasks.models import Task

    if not task_id or not assigned_to:
        return {"error": True, "message": "task_id and assigned_to are required."}

    try:
        task = Task.objects.select_related("project", "workplan", "milestone", "assigned_to", "claimed_by", "created_by").get(pk=task_id)
    except Task.DoesNotExist:
        return {"error": True, "message": f"Task '{task_id}' not found."}

    try:
        user = User.objects.get(username=assigned_to)
    except User.DoesNotExist:
        return {"error": True, "message": f"User '{assigned_to}' not found."}

    task.assigned_to = user
    task.save(update_fields=["assigned_to", "updated_at"])

    return {
        "data": {"task": serialize_task(task)},
        "message": f"Assigned task '{task.title}' to {assigned_to}.",
        "available_actions": ["vtf_task_detail", "vtf_submit_task"],
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_unassign_task(task_id: str) -> dict:
    """Remove assignment from a task."""
    from tasks.models import Task

    if not task_id:
        return {"error": True, "message": "task_id is required."}

    try:
        task = Task.objects.select_related("project", "workplan", "milestone", "assigned_to", "claimed_by", "created_by").get(pk=task_id)
    except Task.DoesNotExist:
        return {"error": True, "message": f"Task '{task_id}' not found."}

    task.assigned_to = None
    task.save(update_fields=["assigned_to", "updated_at"])

    return {
        "data": {"task": serialize_task(task)},
        "message": f"Unassigned task '{task.title}'.",
        "available_actions": ["vtf_task_detail"],
    }
