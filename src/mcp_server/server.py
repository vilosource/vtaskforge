"""
vtf MCP Server entry point.

Bootstrap Django ORM access and create the FastMCP server instance.
Tools are registered in separate modules (P1.3+).

Run as:
    cd src && python -m mcp_server.server
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")

import django  # noqa: E402

django.setup()

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("vtf", instructions="vtaskforge task management server")

if __name__ == "__main__":
    mcp.run(transport="stdio")
