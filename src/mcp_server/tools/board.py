"""
MCP tool: vtf_board_overview

Wraps the get_board_summary() service function and returns a
standard response envelope.
"""
import json

from mcp_server.responses import success_response
from mcp_server.server import mcp
from tasks.services import get_board_summary


@mcp.tool()
def vtf_board_overview(project_id: str = "", workplan_id: str = "") -> str:
    """Get board state summary: task counts by status, attention items,
    pending reviews, and active agents."""
    summary = get_board_summary(
        project_id=project_id or None,
        workplan_id=workplan_id or None,
    )
    return json.dumps(success_response(data=summary))
