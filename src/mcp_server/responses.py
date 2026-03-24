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
    code: str = "",
    details: Optional[Dict] = None,
) -> Dict:
    """
    Build an error response envelope.

    Args:
        message: Actionable human-readable error description.
        code: Machine-readable error code (e.g. "not_found", "invalid_transition").
        details: Additional structured context about the error.

    Returns:
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": {...},
            },
        }
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {},
        },
    }
