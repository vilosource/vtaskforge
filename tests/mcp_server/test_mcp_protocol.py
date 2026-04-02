"""
MCP protocol-level tests.

These tests start the MCP server as a subprocess over stdio and communicate
via the MCP SDK client — exercising the actual JSON-RPC transport, tool
discovery, and async execution path that unit tests skip.

This catches issues like Django's SynchronousOnlyOperation that only surface
when tools run inside FastMCP's async event loop.
"""
import asyncio
import json
import os
import sys

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# The server script that runs in a subprocess.
_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src")

SERVER_SCRIPT = """
import os, sys
sys.path.insert(0, os.environ["_VTF_SRC_DIR"])
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")
from mcp_server.server import mcp
mcp.run(transport="stdio")
"""


def _server_params():
    """StdioServerParameters that spawn the MCP server as a subprocess."""
    env = dict(os.environ)
    env.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")
    env["_VTF_SRC_DIR"] = os.path.abspath(_SRC_DIR)
    return StdioServerParameters(
        command=sys.executable,
        args=["-c", SERVER_SCRIPT],
        env=env,
    )


@pytest.mark.django_db
def test_mcp_initialize_and_list_tools():
    """Server starts, completes MCP handshake, and lists all 9 architect tools."""

    async def run():
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                tool_names = sorted(t.name for t in tools_result.tools)

                assert len(tool_names) == 14
                assert "vtf_board_overview" in tool_names
                assert "vtf_get_context" in tool_names
                assert "vtf_manage_milestone" in tool_names
                assert "vtf_manage_task" in tool_names
                assert "vtf_manage_workplan" in tool_names
                assert "vtf_plan_work" in tool_names
                assert "vtf_workplan_tree" in tool_names
                assert "vtf_manage_task" in tool_names
                assert "vtf_search_tasks" in tool_names
                assert "vtf_manage_workplan" in tool_names
                assert "vtf_task_detail" in tool_names
                assert "vtf_workplan_tree" in tool_names

    asyncio.run(run())


@pytest.mark.django_db
def test_mcp_call_tool_success():
    """Tools return valid JSON responses over the MCP protocol."""

    async def run():
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool("vtf_board_overview", {})
                assert not result.isError
                data = json.loads(result.content[0].text)
                assert data["success"] is True
                assert "data" in data

    asyncio.run(run())


@pytest.mark.django_db
def test_mcp_call_tool_error_path():
    """Error responses are returned as tool results, not MCP-level errors."""

    async def run():
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    "vtf_task_detail", {"task_id": "nonexistent"}
                )
                data = json.loads(result.content[0].text)
                assert data["success"] is False
                assert "not found" in data["message"]
                assert len(data["available_actions"]) > 0

    asyncio.run(run())


@pytest.mark.django_db(transaction=True)
def test_mcp_full_lifecycle():
    """Full executor lifecycle over the MCP protocol."""
    from projects.models import Project

    project = Project.objects.create(name="mcp-protocol-test", id="mcp-proto")
    from workplans.models import Workplan
    workplan = Workplan.objects.create(name="mcp-proto-wp", project=project)

    async def run():
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Create task
                r = await session.call_tool(
                    "vtf_manage_task",
                    {
                        "action": "create",
                        "title": "Protocol test",
                        "project_id": project.id,
                        "workplan_id": workplan.id,
                    },
                )
                d = json.loads(r.content[0].text)
                assert d["success"] is True
                task_id = d["data"]["task"]["id"]
                assert d["data"]["task"]["status"] == "draft"

                # Submit
                r = await session.call_tool(
                    "vtf_manage_task",
                    {"action": "submit", "task_id": task_id},
                )
                d = json.loads(r.content[0].text)
                assert d["data"]["task"]["status"] == "todo"

                # Detail
                r = await session.call_tool(
                    "vtf_task_detail",
                    {"task_id": task_id},
                )
                d = json.loads(r.content[0].text)
                assert d["success"] is True
                assert d["data"]["task"]["status"] == "todo"

                # Cleanup
                r = await session.call_tool(
                    "vtf_manage_task",
                    {"action": "delete", "task_id": task_id},
                )
                d = json.loads(r.content[0].text)
                assert d["success"] is True

    try:
        asyncio.run(run())
    finally:
        project.delete()
