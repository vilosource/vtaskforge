"""
MCP tool: vtf_next_work

Finds the best available task for an agent to work on next.
Uses find_claimable_tasks() from tasks.services, enriched with
dependency status and spec summary.
"""
import json

from mcp_server.responses import success_response
from mcp_server.server import mcp
from tasks.services import find_claimable_tasks, get_task_context


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
