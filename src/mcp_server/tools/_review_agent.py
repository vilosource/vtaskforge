"""
MCP tool: vtf_review_task (P3.4)

Submits a review decision for a task in pending_start_review or
pending_completion_review status. Uses submit_review() from ReviewService.
"""
import json

from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from mcp_server.utils import _suggest_action
from reviews.services import ReviewError, submit_review
from tasks.models import Task

VALID_DECISIONS = {"approved", "changes_requested", "rejected"}
VALID_DECISIONS_LIST = sorted(VALID_DECISIONS)


# @mcp.tool()  # Removed from architect MCP — called by controller via VtfClient
def vtf_review_task(
    task_id: str,
    decision: str,
    reason: str = "",
    reviewer_id: str = "mcp-reviewer",
    reviewer_type: str = "agent",
) -> str:
    """Submit a review for a task that is awaiting review.

    Submit a review for a task that is awaiting review
    (pending_start_review or pending_completion_review). Approve to advance
    the task, or request changes with a reason explaining what needs to be fixed.
    """
    # Validate decision
    if decision not in VALID_DECISIONS:
        suggestion = _suggest_action(decision, VALID_DECISIONS_LIST)
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        return json.dumps(
            error_response(
                message=(
                    f"Invalid decision '{decision}'.{hint} "
                    f"Must be one of: {', '.join(VALID_DECISIONS_LIST)}."
                ),
                data={"task_id": task_id, "decision": decision},
                available_actions=["vtf_task_detail", "vtf_board_overview"],
            )
        )

    # Enforce reviewer != claimer (independent verification)
    try:
        task = Task.objects.get(pk=task_id)
        claimed_username = task.claimed_by.username if task.claimed_by else None
        if claimed_username and reviewer_id == claimed_username:
            return json.dumps(
                error_response(
                    message=(
                        f"Cannot review task {task_id}: reviewer '{reviewer_id}' "
                        f"is the same agent that claimed this task. "
                        f"Reviews must come from an independent agent (e.g., a judge)."
                    ),
                    data={"task_id": task_id, "reviewer_id": reviewer_id,
                          "claimed_by": claimed_username},
                    available_actions=["vtf_task_detail"],
                )
            )
    except Task.DoesNotExist:
        pass  # Let submit_review handle the not-found error

    # Require reason for non-approved decisions
    if decision in {"changes_requested", "rejected"} and not reason:
        return json.dumps(
            error_response(
                message=(
                    f"A reason is required when decision is '{decision}'. "
                    f"Provide a reason explaining what needs to be fixed."
                ),
                data={"task_id": task_id, "decision": decision},
                available_actions=["vtf_task_detail"],
            )
        )

    try:
        from django.contrib.auth.models import User
        reviewer_user = User.objects.filter(username=reviewer_id).first()
        result = submit_review(
            task_id=task_id,
            decision=decision,
            reason=reason,
            reviewer=reviewer_user,
            reviewer_type=reviewer_type,
        )
    except ReviewError as e:
        return json.dumps(
            error_response(
                message=(
                    f"Cannot submit review for task {task_id}: {e.message} "
                    f"Use vtf_board_overview to see which tasks are awaiting review."
                ),
                data={"task_id": task_id},
                available_actions=["vtf_board_overview", "vtf_task_detail"],
            )
        )

    task = result["task"]
    previous_status = result["previous_status"]

    # Build milestone progress if task belongs to a milestone
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
            "auto_completed": False,
        }

    # Build response message
    if decision == "approved":
        status_msg = f"Task {task_id} approved and marked {task.status}."
    else:
        status_msg = f"Task {task_id} returned with '{decision}'."

    if milestone_progress:
        ms_title = milestone_progress["title"]
        ms_pct = milestone_progress["pct"]
        ms_done = milestone_progress["completed"]
        ms_total = milestone_progress["total"]
        message = (
            f"{status_msg} Milestone '{ms_title}' is now {ms_pct}% complete "
            f"({ms_done}/{ms_total} tasks)."
        )
    else:
        message = status_msg

    data = {
        "task": {
            "id": task.id,
            "title": task.title,
            "previous_status": previous_status,
            "status": task.status,
        },
        "milestone_progress": milestone_progress,
    }

    return json.dumps(
        success_response(
            data=data,
            message=message,
            available_actions=["vtf_board_overview", "vtf_next_work"],
        )
    )
