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

def run_server():
    """Start the MCP server using the configured transport.

    Called from docker-compose or __main__. Uses the module-level `mcp`
    instance so tool registrations are on the correct object (avoids the
    __main__ double-import issue with `python -m`).
    """
    transport = os.environ.get("VTF_MCP_TRANSPORT", "stdio")
    if transport == "http":
        import uvicorn

        from mcp_server.http_auth import TokenAuthMiddleware

        host = os.environ.get("VTF_MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("VTF_MCP_PORT", "8002"))
        mcp.settings.host = host
        mcp.settings.port = port

        # Allow connections from Docker service names and k8s DNS.
        # Default allowed_hosts only permits localhost/127.0.0.1.
        allowed_hosts = os.environ.get("VTF_MCP_ALLOWED_HOSTS", "*:*")
        host_list = [h.strip() for h in allowed_hosts.split(",") if h.strip()]
        mcp.settings.transport_security.allowed_hosts = host_list
        # Disable origin check for non-browser API clients (agents).
        mcp.settings.transport_security.enable_dns_rebinding_protection = False

        # Build the Starlette app and attach token auth middleware.
        app = mcp.streamable_http_app()
        app.add_middleware(TokenAuthMiddleware)

        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
