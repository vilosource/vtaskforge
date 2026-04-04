"""MCP tool: vtf_add_note — add a note to a task."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_add_note(task_id: str, text: str) -> dict:
    """Add a note to a task.

    Args:
        task_id: Task to add note to
        text: Note content
    """
    from tasks.models import Note, Task
    from mcp_server.user_context import get_current_user

    if not task_id or not text:
        return {"error": True, "message": "task_id and text are required."}

    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return {"error": True, "message": f"Task '{task_id}' not found."}

    user = get_current_user()
    note = Note.objects.create(task=task, text=text, actor=user)

    from mcp_server.serialization import serialize_note
    return {
        "data": {"note": serialize_note(note)},
        "message": f"Added note to task '{task.title}'.",
        "available_actions": ["vtf_task_detail"],
    }
