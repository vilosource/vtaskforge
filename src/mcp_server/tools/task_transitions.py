"""MCP tools: task state transitions — submit, block, unblock, defer, cancel, delete, recover."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.serialization import serialize_task
from mcp_server.server import mcp


def _get_task(task_id: str):
    """Fetch task with select_related for serialization."""
    from tasks.models import Task
    return Task.objects.select_related(
        "project", "workplan", "milestone", "assigned_to", "claimed_by", "created_by",
    ).get(pk=task_id)


def _transition(task_id: str, target_status: str, trigger_source: str) -> dict:
    """Execute a state machine transition and return serialized result."""
    from tasks.state_machine import perform_transition

    task = _get_task(task_id)
    perform_transition(task, target_status, trigger_source=trigger_source)
    task.refresh_from_db()
    return {
        "data": {"task": serialize_task(task)},
        "message": f"Task '{task.title}' transitioned to {task.status}.",
        "available_actions": ["vtf_task_detail"],
    }


@mcp.tool()
@handle_errors
@serialize_response
def vtf_submit_task(task_id: str) -> dict:
    """Submit a draft task for execution (draft → todo or pending_start_review)."""
    from tasks.review_policy import get_effective_review_flags

    task = _get_task(task_id)
    before_start, _ = get_effective_review_flags(task)
    target = "pending_start_review" if before_start else "todo"
    return _transition(task_id, target, "submit")


@mcp.tool()
@handle_errors
@serialize_response
def vtf_block_task(task_id: str, reason: str = "") -> dict:
    """Block a task (todo/doing → blocked)."""
    return _transition(task_id, "blocked", "block")


@mcp.tool()
@handle_errors
@serialize_response
def vtf_unblock_task(task_id: str) -> dict:
    """Unblock a task (blocked → todo)."""
    return _transition(task_id, "todo", "unblock")


@mcp.tool()
@handle_errors
@serialize_response
def vtf_defer_task(task_id: str) -> dict:
    """Defer a task (any non-terminal → deferred)."""
    return _transition(task_id, "deferred", "defer")


@mcp.tool()
@handle_errors
@serialize_response
def vtf_cancel_task(task_id: str) -> dict:
    """Cancel a task (any non-terminal → cancelled)."""
    return _transition(task_id, "cancelled", "cancel")


@mcp.tool()
@handle_errors
@serialize_response
def vtf_recover_task(task_id: str, target: str = "todo", reason: str = "") -> dict:
    """Recover a task from needs_attention (needs_attention → todo or draft).

    Args:
        task_id: Task to recover
        target: Recovery target — "todo" (re-queue) or "draft" (major rework)
        reason: Reason for recovery (required)
    """
    from tasks.models import Task

    if not reason:
        return {"error": True, "message": "Reason is required for recovery."}
    if target not in ("todo", "draft"):
        return {"error": True, "message": "Target must be 'todo' or 'draft'."}

    task = _get_task(task_id)
    if task.status != "needs_attention":
        return {"error": True, "message": f"Task is '{task.status}', not 'needs_attention'."}

    result = _transition(task_id, target, "recover")

    # Increment retry_count for re-queue, not for major rework
    if target == "todo":
        task.refresh_from_db()
        task.retry_count += 1
        task.save(update_fields=["retry_count"])

    return result


@mcp.tool()
@handle_errors
@serialize_response
def vtf_delete_task(task_id: str) -> dict:
    """Permanently delete a task."""
    from tasks.models import Task

    task = Task.objects.get(pk=task_id)
    title = task.title
    task.delete()
    return {
        "data": {},
        "message": f"Deleted task '{title}' ({task_id}).",
        "available_actions": ["vtf_search_tasks"],
    }
