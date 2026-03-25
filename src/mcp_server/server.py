"""
vtf MCP Server entry point.

Bootstrap Django ORM access and create the FastMCP server instance.
Tools are auto-discovered from mcp_server/tools/ — no manual import lines
needed when adding new tool modules.

Run as:
    cd src && python -m mcp_server.server
"""
import importlib
import inspect
import pkgutil
import os
from typing import Any

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")

import django  # noqa: E402

django.setup()

from asgiref.sync import sync_to_async  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
import mcp_server.tools as _tools_pkg  # noqa: E402


class VtfMCP(FastMCP):
    """FastMCP subclass that automatically wraps sync tool functions with
    sync_to_async so they run safely in a thread pool from the async event
    loop — without disabling Django's async safety check globally."""

    def add_tool(
        self,
        fn: Any,
        name: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if not inspect.iscoroutinefunction(fn):
            fn = sync_to_async(fn, thread_sensitive=False)
        return super().add_tool(fn, name=name, **kwargs)


mcp = VtfMCP("vtf", instructions="vtaskforge task management server")

# Auto-discover and import every module in mcp_server/tools/ (except __init__.py).
# Each module registers its @mcp.tool() decorators on import.
for _module_info in pkgutil.iter_modules(_tools_pkg.__path__):
    importlib.import_module(f"mcp_server.tools.{_module_info.name}")

if __name__ == "__main__":
    mcp.run(transport="stdio")
