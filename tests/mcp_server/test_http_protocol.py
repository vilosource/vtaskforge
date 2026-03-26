"""
MCP HTTP protocol-level tests.

These tests start the MCP server as a subprocess over streamable HTTP transport
and communicate via the MCP SDK HTTP client — exercising the full JSON-RPC
protocol, token authentication, tool discovery, and async execution path.

Unlike the stdio protocol tests, these tests verify the HTTP transport layer
including auth middleware integration.

Server subprocess pattern:
- Uses 'python -c <script>' (not 'python -m') to avoid the __main__ double-import
  problem that occurs when server.py is run as __main__ AND tool modules do
  'from mcp_server.server import mcp' — causing two separate mcp instances.
- The server script mirrors the __main__ block in server.py exactly.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


# ---------------------------------------------------------------------------
# Server startup script
# ---------------------------------------------------------------------------

# This mirrors the HTTP branch of server.py's __main__ block exactly, but
# avoids double-import by running as an inline -c script rather than -m.
_HTTP_SERVER_SCRIPT = """
import sys
sys.path.insert(0, "/app/src")

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")

import django
django.setup()

from mcp_server.server import mcp
from mcp_server.http_auth import TokenAuthMiddleware
import uvicorn

host = os.environ.get("VTF_MCP_HOST", "0.0.0.0")
port = int(os.environ.get("VTF_MCP_PORT", "8002"))
mcp.settings.host = host
mcp.settings.port = port

app = mcp.streamable_http_app()
app.add_middleware(TokenAuthMiddleware)

uvicorn.run(app, host=host, port=port)
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _free_port() -> int:
    """Return a free TCP port by binding to port 0 and releasing it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    """Block until the port accepts connections or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    return False


# ---------------------------------------------------------------------------
# Fixture: running HTTP MCP server (module-scoped, starts once for all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mcp_http_server_process():
    """
    Start the MCP server in HTTP mode as a subprocess.

    Picks a free port and waits for the server to accept connections.
    Yields (host, port, url).
    Kills the subprocess on teardown.

    Scope is "module" so the server starts once for all tests in this file.
    Auth tokens are created per-test to survive pytest transaction flush.

    Uses 'python -c' instead of 'python -m' to avoid the __main__ double-import
    problem where tool modules 'from mcp_server.server import mcp' would get a
    second mcp instance (different from the __main__ one) resulting in 0 tools.
    """
    port = _free_port()
    host = "127.0.0.1"

    env = dict(os.environ)
    env["VTF_MCP_HOST"] = host
    env["VTF_MCP_PORT"] = str(port)
    env.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")

    proc = subprocess.Popen(
        [sys.executable, "-c", _HTTP_SERVER_SCRIPT],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        if not _wait_for_port(host, port, timeout=20.0):
            proc.kill()
            stdout, stderr = proc.communicate(timeout=5)
            raise RuntimeError(
                f"MCP HTTP server did not start on port {port} within 20s.\n"
                f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
            )

        yield host, port, f"http://{host}:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_client(token_key: str) -> httpx.AsyncClient:
    """Return an httpx.AsyncClient configured with token auth."""
    return httpx.AsyncClient(
        headers={"Authorization": f"Token {token_key}"},
        timeout=30.0,
    )


# ---------------------------------------------------------------------------
# test_http_initialize_and_list_tools
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_initialize_and_list_tools(mcp_http_server_process):
    """Server starts over HTTP, completes MCP handshake, and lists all 12 tools."""
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token

    _host, _port, url = mcp_http_server_process

    # Create user + token committed to DB so the subprocess server can validate.
    user = User.objects.create_user(username="mcp-http-test-tools", password="x")
    token = Token.objects.create(user=user)
    token_key = token.key

    async def run():
        async with _make_http_client(token_key) as http_client:
            async with streamable_http_client(url=url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tools_result = await session.list_tools()
                    tool_names = sorted(t.name for t in tools_result.tools)

                    assert len(tool_names) == 12
                    assert "vtf_board_overview" in tool_names
                    assert "vtf_claim_and_start" in tool_names
                    assert "vtf_manage_milestone" in tool_names
                    assert "vtf_manage_task" in tool_names
                    assert "vtf_manage_workplan" in tool_names
                    assert "vtf_next_work" in tool_names
                    assert "vtf_report_progress" in tool_names
                    assert "vtf_review_task" in tool_names
                    assert "vtf_search_tasks" in tool_names
                    assert "vtf_submit_work" in tool_names
                    assert "vtf_task_detail" in tool_names
                    assert "vtf_workplan_tree" in tool_names

    asyncio.run(run())


# ---------------------------------------------------------------------------
# test_http_call_tool_success
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_call_tool_success(mcp_http_server_process):
    """Tools return valid JSON success responses over the MCP HTTP transport."""
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token

    _host, _port, url = mcp_http_server_process

    user = User.objects.create_user(username="mcp-http-test-success", password="x")
    token = Token.objects.create(user=user)
    token_key = token.key

    async def run():
        async with _make_http_client(token_key) as http_client:
            async with streamable_http_client(url=url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result = await session.call_tool("vtf_board_overview", {})
                    assert not result.isError
                    data = json.loads(result.content[0].text)
                    assert data["success"] is True
                    assert "data" in data

    asyncio.run(run())


# ---------------------------------------------------------------------------
# test_http_call_tool_error
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_call_tool_error(mcp_http_server_process):
    """Error responses for nonexistent tasks are returned as tool results, not MCP errors."""
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token

    _host, _port, url = mcp_http_server_process

    user = User.objects.create_user(username="mcp-http-test-error", password="x")
    token = Token.objects.create(user=user)
    token_key = token.key

    async def run():
        async with _make_http_client(token_key) as http_client:
            async with streamable_http_client(url=url, http_client=http_client) as (read, write, _):
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


# ---------------------------------------------------------------------------
# test_http_full_lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_full_lifecycle(mcp_http_server_process):
    """Full executor lifecycle over the MCP HTTP transport."""
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project

    _host, _port, url = mcp_http_server_process

    user = User.objects.create_user(username="mcp-http-test-lifecycle", password="x")
    token = Token.objects.create(user=user)
    token_key = token.key

    project = Project.objects.create(name="mcp-http-protocol-test", id="mcp-http-proto")

    async def run():
        async with _make_http_client(token_key) as http_client:
            async with streamable_http_client(url=url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Create task
                    r = await session.call_tool(
                        "vtf_manage_task",
                        {
                            "action": "create",
                            "title": "HTTP protocol test",
                            "project_id": project.id,
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

                    # Claim
                    r = await session.call_tool(
                        "vtf_claim_and_start",
                        {"task_id": task_id, "agent_id": "http-proto-agent"},
                    )
                    d = json.loads(r.content[0].text)
                    assert d["success"] is True
                    assert d["data"]["task"]["status"] == "doing"

                    # Progress
                    r = await session.call_tool(
                        "vtf_report_progress",
                        {"task_id": task_id, "note": "halfway via HTTP"},
                    )
                    d = json.loads(r.content[0].text)
                    assert d["data"]["note_added"] is True

                    # Submit work
                    r = await session.call_tool(
                        "vtf_submit_work",
                        {"task_id": task_id, "completion_note": "done via HTTP"},
                    )
                    d = json.loads(r.content[0].text)
                    assert d["success"] is True
                    final_status = d["data"]["task"]["status"]
                    assert final_status in ("done", "pending_completion_review")

                    # Cleanup
                    r = await session.call_tool(
                        "vtf_manage_task",
                        {"action": "delete", "task_id": task_id},
                    )
                    d = json.loads(r.content[0].text)
                    assert d["success"] is True

    asyncio.run(run())
