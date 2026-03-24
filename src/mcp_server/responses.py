"""
MCP Server shared response formatting.

Provides success_response() and error_response() helpers that produce
the standard envelope format defined in docs/vtf-mcp-server-SPECIFICATION.md
section 4.1.

Every MCP tool response should use one of these helpers.
"""
from typing import Any, Dict, List, Optional


def success_response(
    data: Any,
    message: str = "",
    available_actions: Optional[List[str]] = None,
) -> Dict:
    """
    Build a successful response envelope.

    Args:
        data: The primary payload (task, list, summary, etc.)
        message: Human-readable summary for the agent.
        available_actions: List of MCP tool names the agent can call next.

    Returns:
        {
            "success": True,
            "data": data,
            "message": message,
            "available_actions": [...],
        }
    """
    return {
        "success": True,
        "data": data,
        "message": message,
        "available_actions": available_actions if available_actions is not None else [],
    }


def error_response(
    message: str,
    data: Optional[Dict] = None,
    available_actions: Optional[List[str]] = None,
) -> Dict:
    """
    Build an error response envelope.

    Args:
        message: Actionable human-readable error description (what went wrong,
                 why, and what to do instead).
        data: Additional structured context about the error (e.g. task_id,
              current_status). Goes inside the standard ``data`` key.
        available_actions: List of MCP tool names the agent can call next.

    Returns:
        {
            "success": False,
            "data": {...},
            "message": "...",
            "available_actions": [...],
        }
    """
    return {
        "success": False,
        "data": data if data is not None else {},
        "message": message,
        "available_actions": available_actions if available_actions is not None else [],
    }
