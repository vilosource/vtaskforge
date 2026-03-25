"""
MCP server utilities.

Provides async_tool decorator for wrapping sync tool functions so they run
safely in a thread pool when called from FastMCP's async event loop.

Note: The primary async wrapping for registered tools is done via post-
registration patching in server.py. This module provides a standalone
decorator for cases where explicit wrapping is preferred.
"""
import functools

from asgiref.sync import sync_to_async


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
