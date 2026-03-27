"""
MCP tool: vtf_task_detail (P3.2)

Returns complete details for a single task including spec, dependencies,
reviews, recent events, notes, available transitions, and a contextual message.
"""
import json

from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from tasks.models import Task
from tasks.services import get_available_actions, get_task_context


@mcp.tool()
def vtf_task_detail(task_id: str) -> str:
    """Get complete details for a specific task including its full spec, dependency status,
    review history, event timeline, and what actions are currently available. Use this when
    you need the full picture before acting on a task.
    """
    # Fetch task — return error if not found
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return json.dumps(
            error_response(
                message=f"Task {task_id} not found.",
                data={"task_id": task_id},
                available_actions=["vtf_next_work", "vtf_board_overview"],
            )
        )

    # Get base context from service (includes reviews, events, notes, deps)
    context = get_task_context(task_id)

    task_info = context["task"]

    # Limit recent_events to last 10
    recent_events = context["events"][:10]

    # Filter notes from events: progress_note, completion_note, and note types
    notes = [
        e for e in context["events"]
        if e["event_type"] in ("progress_note", "completion_note", "note")
    ]

    # Get available state-machine transitions for this task
    available_transitions = get_available_actions(task)

    # Build contextual message based on task status
    status = task_info["status"]
    title = task_info["title"]

    if status == "todo":
        message = f"Task {task_id} '{title}' is ready to be claimed."
    elif status == "doing":
        claimed_by = task_info.get("claimed_by") or "unknown"
        message = f"Task {task_id} '{title}' is in progress, claimed by {claimed_by}."
    elif status == "done":
        message = f"Task {task_id} '{title}' is complete."
    elif status == "blocked":
        message = f"Task {task_id} '{title}' is blocked."
    elif status == "needs_attention":
        message = f"Task {task_id} '{title}' needs attention."
    elif status == "pending_start_review":
        message = f"Task {task_id} '{title}' is awaiting start review."
    elif status == "pending_completion_review":
        message = f"Task {task_id} '{title}' is awaiting completion review."
    elif status == "changes_requested":
        # Include most recent review reason if available
        reviews = context["reviews"]
        if reviews:
            latest_reason = reviews[-1].get("reason", "")
            message = (
                f"Task {task_id} has changes requested: '{latest_reason}'."
                " Ready to be reclaimed for rework."
            )
        else:
            message = f"Task {task_id} '{title}' has changes requested. Ready to be reclaimed for rework."
    elif status == "draft":
        message = f"Task {task_id} '{title}' is in draft state."
    elif status == "deferred":
        message = f"Task {task_id} '{title}' has been deferred."
    elif status == "cancelled":
        message = f"Task {task_id} '{title}' has been cancelled."
    else:
        message = f"Task {task_id} '{title}' is in '{status}' status."

    data = {
        "task": task_info,
        "spec": context["spec"],
        "acceptance_criteria": task_info.get("acceptance_criteria"),
        "test_command": task_info.get("test_command"),
        "execution": {
            "agent_model": task_info.get("agent_model"),
            "judge": task_info.get("judge"),
            "isolation": task_info.get("isolation"),
        },
        "dependencies": context["dependencies"],
        "reviews": context["reviews"],
        "recent_events": recent_events,
        "notes": notes,
    }

    # Build available_actions list from transitions
    available_actions = []
    for transition in available_transitions:
        if transition == "doing":
            available_actions.append("vtf_claim_and_start")
        else:
            available_actions.append(f"vtf_manage_task(action={transition})")

    return json.dumps(
        success_response(
            data=data,
            message=message,
            available_actions=available_actions,
        )
    )
