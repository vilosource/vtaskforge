"""MCP tool: vtf_board_overview — board summary with counts and attention items."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_board_overview(project_id: str = "", workplan_id: str = "") -> dict:
    """Get board state summary: task counts by status, attention items,
    pending reviews, and active agents."""
    from tasks.services import get_board_summary

    summary = get_board_summary(
        project_id=project_id or None,
        workplan_id=workplan_id or None,
    )
    return {
        "data": summary,
        "message": f"Board: {sum(summary.get('counts', {}).values())} total tasks.",
    }
