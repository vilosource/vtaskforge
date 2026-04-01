"""
MCP server utilities.

Provides async_tool decorator for wrapping sync tool functions so they run
safely in a thread pool when called from FastMCP's async event loop.

Note: The primary async wrapping for registered tools is done via post-
registration patching in server.py. This module provides a standalone
decorator for cases where explicit wrapping is preferred.

Also provides _suggest_action for fuzzy "did you mean" hints in error messages.
"""
import functools

from asgiref.sync import sync_to_async


def _suggest_action(invalid_action: str, valid_actions: list) -> str | None:
    """Return the closest valid action as a fuzzy suggestion, or None.

    Strategy (no external dependencies):
    1. Strip common verb suffixes ("ed", "ing", "s") from the input.
    2. If the stripped form exactly matches a valid action, return it.
    3. Fall back to checking if any valid action starts with the stripped input
       (prefix match) — handles truncations like "approv" → "approved".
    4. If nothing matches, return None.
    """
    suffixes = ["ing", "led", "red", "ted", "ned", "ed", "s"]
    stripped = invalid_action
    for suffix in suffixes:
        if invalid_action.endswith(suffix) and len(invalid_action) > len(suffix):
            candidate = invalid_action[: -len(suffix)]
            if candidate in valid_actions:
                return candidate
            stripped = candidate
            break

    # Prefix match: any valid action that starts with stripped form
    for action in valid_actions:
        if action.startswith(stripped) and stripped:
            return action

    return None


def parse_test_command(raw: str) -> dict | None:
    """Parse test_command: accept plain string or JSON object.

    Plain string is wrapped as {"command": "..."}.
    JSON string is parsed as-is.
    Empty string returns None.
    """
    import json
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return {"command": raw}
    except json.JSONDecodeError:
        return {"command": raw}


def async_tool(fn):
    """Wrap a sync tool function for safe async execution in FastMCP.

    Returns an async wrapper that runs the original sync function in a
    thread pool via asgiref's sync_to_async. Uses thread_sensitive=False
    to allow true thread parallelism.

    The original sync function is accessible via wrapper.__wrapped__ for
    direct calls in tests or other sync contexts.

    Example::

        @mcp.tool()
        @async_tool
        def my_tool(param: str) -> str:
            return do_sync_work(param)
    """
    _async_fn = sync_to_async(fn, thread_sensitive=False)

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        return await _async_fn(*args, **kwargs)

    return wrapper
