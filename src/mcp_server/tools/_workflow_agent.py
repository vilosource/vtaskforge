"""
MCP tools: vtf_next_work (P2.1), vtf_claim_and_start (P2.2), vtf_report_progress (P2.3),
vtf_submit_work (P2.4)

vtf_next_work — finds the best available task for an agent to work on next.
vtf_claim_and_start — atomically claims a task and returns full execution context.
vtf_report_progress — extends claim heartbeat and optionally logs a progress note.
vtf_submit_work — completes a task and optionally triggers review.

All tools use service functions from tasks.services.
"""
import json
from datetime import timedelta

from django.utils import timezone

from events.services import record_event
from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from tasks.models import Task
from tasks.review_policy import get_effective_review_flags
from tasks.services import ClaimError, claim_task, find_claimable_tasks, get_task_context
from tasks.state_machine import perform_transition
from tasks.views import DEFAULT_CLAIM_TIMEOUT_MINUTES


# @mcp.tool()  # Removed from architect MCP — called by controller via VtfClient
def vtf_next_work(project_id: str = "", tags: str = "", agent_id: str = "") -> str:
    """Find the best available task to work on next.

    Matches agent capabilities (tags) against task requirements, checks all
    dependencies are resolved, and returns the best candidate with full context.
    Use this instead of manually searching and checking dependencies.
    """
    # Convert empty strings to None for service layer
    project_id_filter = project_id or None
    agent_id_filter = agent_id or None

    # Parse comma-separated tags string into a list
    tags_list = None
    if tags:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Find all claimable tasks matching filters
    claimable = find_claimable_tasks(
        project_id=project_id_filter,
        tags=tags_list,
        agent_id=agent_id_filter,
    )

    # Evaluate as list (queryset may not support len() without extra query)
    claimable_list = list(claimable)

    if not claimable_list:
        # No work available — return helpful message
        tags_display = tags_list if tags_list else []
        return json.dumps(
            success_response(
                data=None,
                message=(
                    f"No claimable tasks matching tags {tags_display}."
                    " Use vtf_board_overview to see overall project state."
                ),
                available_actions=["vtf_board_overview"],
            )
        )

    # Get the best candidate (first task in the list)
    best = claimable_list[0]
    alternatives_count = len(claimable_list) - 1

    # Enrich with full task context
    context = get_task_context(best.id)

    # Build response data matching spec section 4.3
    data = {
        "task": context["task"],
        "spec_summary": context["spec"],
        "dependencies": context["dependencies"],
        "alternatives": {
            "count": alternatives_count,
            "message": f"{alternatives_count} other task{'s' if alternatives_count != 1 else ''} are also claimable",
        },
    }

    task_title = best.title
    message = (
        f"Recommended: '{best.id}: {task_title}' (all deps resolved)."
        f" {alternatives_count} other option{'s' if alternatives_count != 1 else ''} available."
    )

    return json.dumps(
        success_response(
            data=data,
            message=message,
            available_actions=["claim_and_start"],
        )
    )


# @mcp.tool()  # Removed from architect MCP — called by controller via VtfClient
def vtf_claim_and_start(task_id: str, agent_id: str, tags: str = "") -> str:
    """Claim a specific task and receive full execution context.

    Claim a specific task and receive the full execution context: spec,
    dependencies, test commands, and isolation mode. After calling this, you
    have everything needed to start implementing. The task status will change
    to 'doing'.
    """
    # Parse comma-separated tags string into a list
    tags_list = []
    if tags:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    try:
        # Atomically claim the task via the service layer
        claim_task(task_id, agent_id, agent_tags=tags_list)
    except Task.DoesNotExist:
        return json.dumps(
            error_response(
                message=f"Task {task_id} not found. Use vtf_next_work to find an available task.",
                data={"task_id": task_id},
                available_actions=["vtf_next_work", "vtf_search_tasks"],
            )
        )
    except ClaimError as e:
        # Build actionable error messages and suggest appropriate next steps
        if e.code == "tag_mismatch":
            message = (
                f"Cannot claim task {task_id}: agent tags {tags_list} do not satisfy "
                f"task requirements {e.details.get('requires', [])}. "
                f"Use vtf_next_work to find a task matching your tags."
            )
            actions = ["vtf_next_work"]
        elif e.code == "deps_unmet":
            dep_id = e.details.get("dependency_id", "unknown")
            dep_status = e.details.get("dependency_status", "unknown")
            message = (
                f"Cannot claim task {task_id}: dependency {dep_id} is in "
                f"'{dep_status}' status, not 'done'. Wait for it to complete "
                f"or use vtf_next_work to pick a different task."
            )
            actions = ["vtf_next_work", f"vtf_task_detail(task_id={dep_id})"]
        elif e.code == "ALREADY_CLAIMED":
            current_status = e.details.get("current_status", "unknown")
            message = (
                f"Cannot claim task {task_id}: it is in '{current_status}' status "
                f"and cannot be claimed. Use vtf_next_work to find an available task."
            )
            actions = ["vtf_next_work"]
        elif e.code == "FORBIDDEN":
            message = (
                f"Cannot claim task {task_id}: it is assigned to another agent. "
                f"Use vtf_next_work to find a task available for your agent."
            )
            actions = ["vtf_next_work"]
        else:
            message = (
                f"Cannot claim task {task_id}: {e.message}. "
                f"Use vtf_next_work to find an available task."
            )
            actions = ["vtf_next_work"]

        return json.dumps(
            error_response(
                message=message,
                data={"task_id": task_id, **e.details},
                available_actions=actions,
            )
        )

    # Claim succeeded — fetch full context for the response
    context = get_task_context(task_id)

    task_info = context["task"]
    claim_expires_at = task_info.get("claim_expires_at", "")
    judge_required = task_info.get("judge", False)

    judge_note = " Judge review required on completion." if judge_required else ""
    expires_display = f" Claim expires at {claim_expires_at}." if claim_expires_at else ""

    message = (
        f"Claimed task {task_id}.{expires_display}{judge_note}"
    )

    data = {
        "task": task_info,
        "spec": context["spec"],
        "dependencies": context["dependencies"],
        "test_command": task_info.get("test_command"),
        "acceptance_criteria": task_info.get("acceptance_criteria"),
        "isolation": task_info.get("isolation"),
        "agent_model": task_info.get("agent_model"),
        "judge": task_info.get("judge"),
    }

    return json.dumps(
        success_response(
            data=data,
            message=message,
            available_actions=["vtf_report_progress", "vtf_submit_work"],
        )
    )


# @mcp.tool()  # Removed from architect MCP — called by controller via VtfClient
def vtf_report_progress(task_id: str, note: str = "", agent_id: str = "") -> str:
    """Report progress on a claimed task. Extends claim timeout and optionally adds a note.

    Call this periodically during long-running tasks to keep your claim alive and
    provide visibility to supervisors. Extends the claim expiry by the task's
    configured timeout (default 30 minutes from now).
    """
    # Fetch the task
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return json.dumps(
            error_response(
                message=f"Task {task_id} not found.",
                data={"task_id": task_id},
                available_actions=["vtf_next_work"],
            )
        )

    # Verify task is in doing status
    if task.status != "doing":
        return json.dumps(
            error_response(
                message=(
                    f"Cannot report progress on task {task_id}: task is in '{task.status}' status, "
                    f"not 'doing'. Only claimed tasks in 'doing' status support heartbeats."
                ),
                data={"task_id": task_id, "current_status": task.status},
                available_actions=["vtf_next_work", "vtf_claim_and_start"],
            )
        )

    # Extend claim_expires_at (matches heartbeat action in views.py)
    timeout = task.claim_timeout or timedelta(minutes=DEFAULT_CLAIM_TIMEOUT_MINUTES)
    task.claim_expires_at = timezone.now() + timeout
    task.save(update_fields=["claim_expires_at", "updated_at"])

    # Optionally record a progress note as an event
    note_added = False
    if note:
        actor_id = agent_id or (task.claimed_by.username if task.claimed_by else "")
        record_event(
            task,
            "progress_note",
            data={"note": note, "agent_id": actor_id},
            trigger_source="progress",
        )
        note_added = True

    claim_expires_display = task.claim_expires_at.strftime("%H:%M UTC") if task.claim_expires_at else ""
    note_msg = " Note recorded." if note_added else ""
    message = f"Heartbeat received. Claim extended to {claim_expires_display}.{note_msg}"

    data = {
        "task_id": task_id,
        "claim_expires_at": task.claim_expires_at.isoformat() if task.claim_expires_at else None,
        "note_added": note_added,
    }

    return json.dumps(
        success_response(
            data=data,
            message=message,
            available_actions=["vtf_report_progress", "vtf_submit_work", "vtf_manage_task(action=fail)"],
        )
    )


# @mcp.tool()  # Removed from architect MCP — called by controller via VtfClient
def vtf_submit_work(task_id: str, completion_note: str = "", agent_id: str = "") -> str:
    """Submit completed work for a task. Triggers review if configured.

    Marks the task as complete. If the task has review-on-completion enabled,
    it will move to 'pending_completion_review'. Otherwise it moves directly
    to 'done'. Optionally add a completion note describing what was done.
    """
    # Fetch the task
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return json.dumps(
            error_response(
                message=f"Task {task_id} not found.",
                data={"task_id": task_id},
                available_actions=["vtf_next_work"],
            )
        )

    # Verify task is in doing status
    if task.status != "doing":
        return json.dumps(
            error_response(
                message=(
                    f"Cannot submit work for task {task_id}: task is in '{task.status}' status, "
                    f"not 'doing'. Only claimed tasks in 'doing' status can be submitted."
                ),
                data={"task_id": task_id, "current_status": task.status},
                available_actions=["vtf_next_work", "vtf_claim_and_start"],
            )
        )

    # Optionally record a completion note before transitioning
    if completion_note:
        actor_id = agent_id or (task.claimed_by.username if task.claimed_by else "")
        record_event(
            task,
            "completion_note",
            data={"note": completion_note, "agent_id": actor_id},
            trigger_source="complete",
        )

    # Determine target status via review policy
    _, needs_review_on_completion = get_effective_review_flags(task)
    target_status = "pending_completion_review" if needs_review_on_completion else "done"

    # Perform state transition via state machine (handles event recording)
    perform_transition(task, target_status, trigger_source="complete")

    # Refresh to pick up any changes from transition
    task.refresh_from_db()

    # Build milestone progress if the task has a milestone
    milestone_progress = None
    if task.milestone:
        milestone = task.milestone
        milestone_tasks = Task.objects.filter(milestone=milestone)
        total = milestone_tasks.count()
        completed = milestone_tasks.filter(status="done").count()
        pct = round((completed / total) * 100) if total > 0 else 0
        milestone_progress = {
            "id": milestone.id,
            "title": milestone.name,
            "completed": completed,
            "total": total,
            "pct": pct,
        }

    # Build response message
    if target_status == "pending_completion_review":
        status_msg = f"Task {task_id} submitted for review (pending_completion_review)."
    else:
        status_msg = f"Task {task_id} marked as done."

    if milestone_progress:
        ms_title = milestone_progress["title"]
        ms_pct = milestone_progress["pct"]
        ms_done = milestone_progress["completed"]
        ms_total = milestone_progress["total"]
        message = f"{status_msg} Milestone '{ms_title}' is now {ms_pct}% complete ({ms_done}/{ms_total} tasks)."
    else:
        message = status_msg

    data = {
        "task": {
            "id": task.id,
            "title": task.title,
            "status": task.status,
        },
        "review_required": needs_review_on_completion,
        "milestone_progress": milestone_progress,
    }

    return json.dumps(
        success_response(
            data=data,
            message=message,
            available_actions=["vtf_next_work", "vtf_board_overview"],
        )
    )
