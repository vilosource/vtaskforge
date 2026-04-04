"""MCP tool: vtf_task_detail — complete task details with v2 serialized data."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_task_detail(task_id: str) -> dict:
    """Get complete details for a specific task including its full spec, dependency status,
    review history, event timeline, and what actions are currently available.
    """
    from tasks.models import Task
    from tasks.services import get_task_context_v2, get_available_actions

    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return {"error": True, "message": f"Task {task_id} not found."}

    context = get_task_context_v2(task_id)
    task_data = context["task"]

    status = task_data.get("status", "")
    title = task_data.get("title", "")

    messages = {
        "todo": f"Task '{title}' is ready to be claimed.",
        "doing": f"Task '{title}' is in progress.",
        "done": f"Task '{title}' is complete.",
        "blocked": f"Task '{title}' is blocked.",
        "needs_attention": f"Task '{title}' needs attention.",
        "pending_start_review": f"Task '{title}' is awaiting start review.",
        "pending_completion_review": f"Task '{title}' is awaiting completion review.",
        "changes_requested": f"Task '{title}' has changes requested.",
        "draft": f"Task '{title}' is in draft state.",
        "deferred": f"Task '{title}' has been deferred.",
        "cancelled": f"Task '{title}' has been cancelled.",
    }
    message = messages.get(status, f"Task '{title}' is in '{status}' status.")

    available_transitions = get_available_actions(task)
    transition_to_tool = {
        "doing": "vtf_assign_task",
        "todo": "vtf_submit_task",
        "blocked": "vtf_block_task",
        "cancelled": "vtf_cancel_task",
        "deferred": "vtf_defer_task",
    }
    available_actions = [transition_to_tool.get(t, "vtf_task_detail") for t in available_transitions]

    return {
        "data": {
            "task": task_data,
            "spec": context["spec"],
            "dependencies": context["dependencies"],
            "reviews": context["reviews"],
            "events": context.get("events", [])[:10],
            "notes": context["notes"],
        },
        "message": message,
        "available_actions": available_actions,
    }
