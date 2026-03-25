"""
MCP tools: vtf_next_work (P2.1), vtf_claim_and_start (P2.2)

vtf_next_work — finds the best available task for an agent to work on next.
vtf_claim_and_start — atomically claims a task and returns full execution context.

Both tools use service functions from tasks.services.
"""
import json

from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from tasks.services import ClaimError, claim_task, find_claimable_tasks, get_task_context


@mcp.tool()
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


@mcp.tool()
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
    except Exception:
        raise

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
