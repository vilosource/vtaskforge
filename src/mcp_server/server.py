"""
vtf MCP Server entry point.

Bootstrap Django ORM access and create the FastMCP server instance.
Tools are auto-discovered from mcp_server/tools/ — no manual import lines
needed when adding new tool modules.

Run as:
    cd src && python -m mcp_server.server
"""
import importlib
import pkgutil
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")

import django  # noqa: E402

django.setup()

from mcp.server.fastmcp import FastMCP  # noqa: E402
import mcp_server.tools as _tools_pkg  # noqa: E402

mcp = FastMCP("vtf", instructions="vtaskforge task management server")

# Auto-discover and import every module in mcp_server/tools/ (except __init__.py).
# Each module registers its @mcp.tool() decorators on import.
for _module_info in pkgutil.iter_modules(_tools_pkg.__path__):
    importlib.import_module(f"mcp_server.tools.{_module_info.name}")

if __name__ == "__main__":
    mcp.run(transport="stdio")
