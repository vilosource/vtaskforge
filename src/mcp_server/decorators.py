"""Cross-cutting decorators for MCP tools.

@handle_errors — catches exceptions, returns standardized error JSON
@serialize_response — wraps tool return dict in MCP envelope + json.dumps
"""
import json
import functools
import logging

from .responses import error_response, success_response

logger = logging.getLogger(__name__)


def handle_errors(func):
    """Decorator that catches all exceptions and returns error JSON.

    Handles specific exception types with appropriate messages.
    Unknown exceptions get a generic message + logging.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            # Map known exception types to messages
            exc_type = type(exc).__name__
            message = str(exc)

            if "DoesNotExist" in exc_type:
                message = f"Not found: {message}"
            elif "GuardViolation" in exc_type:
                message = f"Cannot perform action: {message}"
            elif "InvalidTransition" in exc_type:
                message = f"Invalid state transition: {message}"
            elif "ClaimError" in exc_type:
                message = f"Claim failed: {message}"
            else:
                logger.exception(f"Unhandled error in {func.__name__}: {exc}")

            return json.dumps(error_response(message=message))

    return wrapper


def serialize_response(func):
    """Decorator that wraps tool return dict in MCP envelope + json.dumps.

    The tool function returns a plain dict with:
        - data: entity data (required)
        - message: human-readable message (required)
        - available_actions: list of next tool names (optional)
        - error: if True, wraps as error response

    This decorator handles the json.dumps() call — tools never call it.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        if not isinstance(result, dict):
            return result  # Already serialized (e.g., from @handle_errors)

        if result.get("error"):
            return json.dumps(error_response(
                message=result.get("message", "An error occurred"),
            ))

        return json.dumps(success_response(
            data=result.get("data", {}),
            message=result.get("message", ""),
            available_actions=result.get("available_actions"),
        ))

    return wrapper


def require_project_access(project_id_param: str = "project_id"):
    """Decorator that checks project membership before tool execution.

    Extracts project_id from the tool's kwargs using the specified parameter name.
    Staff users bypass the check. Returns error if user is not a member.

    Args:
        project_id_param: Name of the kwarg containing the project ID
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from mcp_server.user_context import get_current_user
            from mcp_server.project_context import get_default_project
            from core.authorization import check_project_membership

            user = get_current_user()
            if not user:
                return json.dumps(error_response(message="Authentication required."))

            if user.is_staff:
                return func(*args, **kwargs)

            pid = kwargs.get(project_id_param, "") or get_default_project()
            if pid and not check_project_membership(user, pid):
                return json.dumps(error_response(
                    message=f"You are not a member of project '{pid}'.",
                ))

            return func(*args, **kwargs)

        return wrapper

    return decorator
