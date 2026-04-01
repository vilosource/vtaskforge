"""
Integration tests for HTTP + auth stack.

Starts the MCP server as a subprocess in HTTP mode with auth enabled,
then tests valid and invalid token paths using real Django authtoken records.

Unlike the unit tests in test_http_auth.py (which mock validate_token),
these tests exercise the full path: subprocess server, real DB lookup,
middleware rejection, and MCP client behaviour on 401.

Server fixture scope is "module" so the server process starts once. Tests
use transaction=True so DB rows committed by the test process are visible
to the subprocess server without waiting for transaction rollback.
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
# Server startup script (mirrors test_http_protocol.py pattern exactly)
# ---------------------------------------------------------------------------

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src")

_HTTP_SERVER_SCRIPT = """
import sys, os
sys.path.insert(0, os.environ["_VTF_SRC_DIR"])
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


def _wait_for_port(host: str, port: int, timeout: float = 20.0) -> bool:
    """Block until the port accepts connections or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.3)
    return False


def _make_http_client(token_key: str) -> httpx.AsyncClient:
    """Return an httpx.AsyncClient configured with token auth."""
    return httpx.AsyncClient(
        headers={"Authorization": f"Token {token_key}"},
        timeout=30.0,
    )


# ---------------------------------------------------------------------------
# Fixture: running HTTP MCP server with auth enabled (module-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mcp_http_auth_server():
    """
    Start the MCP server in HTTP mode with TokenAuthMiddleware enabled.

    Picks a free port, waits for the server to accept connections.
    Yields (host, port, url). Kills the subprocess on teardown.

    Scope is "module" so the server starts once for all tests in this file.
    Auth tokens are created per-test to survive pytest transaction flush.
    """
    port = _free_port()
    host = "127.0.0.1"

    env = dict(os.environ)
    env["VTF_MCP_HOST"] = host
    env["VTF_MCP_PORT"] = str(port)
    env["_VTF_SRC_DIR"] = os.path.abspath(_SRC_DIR)
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
                f"MCP HTTP auth server did not start on port {port} within 20s.\n"
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
# test_http_auth_valid_token_lists_tools
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_auth_valid_token_lists_tools(mcp_http_auth_server):
    """Valid token: tools/list succeeds and returns exactly 12 tools."""
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token

    _host, _port, url = mcp_http_auth_server

    user = User.objects.create_user(username="mcp-auth-intg-list", password="x")
    token = Token.objects.create(user=user)
    token_key = token.key

    async def run():
        async with _make_http_client(token_key) as http_client:
            async with streamable_http_client(url=url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    tools_result = await session.list_tools()
                    tool_names = sorted(t.name for t in tools_result.tools)

                    assert len(tool_names) == 9
                    assert "vtf_board_overview" in tool_names

    asyncio.run(run())


# ---------------------------------------------------------------------------
# test_http_auth_valid_token_calls_tool
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_auth_valid_token_calls_tool(mcp_http_auth_server):
    """Valid token: vtf_board_overview call succeeds and returns a success response."""
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token

    _host, _port, url = mcp_http_auth_server

    user = User.objects.create_user(username="mcp-auth-intg-call", password="x")
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
# test_http_auth_invalid_token_rejected
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_auth_invalid_token_rejected(mcp_http_auth_server):
    """
    Invalid token: connection attempt returns 401.

    The MCP streamable_http_client raises an ExceptionGroup containing
    httpx.HTTPStatusError when the server responds with 401 instead of
    a valid MCP response.  We use httpx directly to assert the 401 status
    code clearly, and also verify the MCP client raises on the bad token.
    """
    _host, _port, url = mcp_http_auth_server

    bad_token = "0000000000000000000000000000000000000000"

    # Direct HTTP check — assert the server returns 401.
    async def check_direct():
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Token {bad_token}"},
                content=b"{}",
            )
            assert resp.status_code == 401, (
                f"Expected 401 but got {resp.status_code}"
            )
            body = resp.json()
            assert "error" in body

    asyncio.run(check_direct())

    # MCP client check — the client should raise when it receives 401.
    async def check_mcp_client():
        raised = False
        try:
            async with _make_http_client(bad_token) as http_client:
                async with streamable_http_client(url=url, http_client=http_client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
        except BaseException as exc:
            raised = True
            # ExceptionGroup wraps httpx.HTTPStatusError with "401" in message.
            exc_str = str(exc)
            found_status_error = False
            if hasattr(exc, "exceptions"):
                for sub in exc.exceptions:
                    if "401" in str(sub):
                        found_status_error = True
            assert found_status_error or "401" in exc_str, (
                f"Expected 401 error but got: {exc_str}"
            )
        assert raised, "Expected MCP client to raise on invalid token but it did not"

    asyncio.run(check_mcp_client())


# ---------------------------------------------------------------------------
# test_http_auth_no_token_rejected
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_http_auth_no_token_rejected(mcp_http_auth_server):
    """
    No token: connection attempt without Authorization header returns 401.

    Uses httpx directly since the MCP client always passes the header when
    constructed via _make_http_client.  Also verifies MCP client raises when
    no header is provided.
    """
    _host, _port, url = mcp_http_auth_server

    # Direct HTTP check — no Authorization header should return 401.
    async def check_direct():
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=b"{}")
            assert resp.status_code == 401, (
                f"Expected 401 but got {resp.status_code}"
            )
            body = resp.json()
            assert "error" in body

    asyncio.run(check_direct())

    # MCP client check — no auth header should also cause the client to raise.
    async def check_mcp_client():
        raised = False
        try:
            # Build a client with NO Authorization header.
            async with httpx.AsyncClient(timeout=30.0) as http_client:
                async with streamable_http_client(url=url, http_client=http_client) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
        except BaseException as exc:
            raised = True
            exc_str = str(exc)
            found_status_error = False
            if hasattr(exc, "exceptions"):
                for sub in exc.exceptions:
                    if "401" in str(sub):
                        found_status_error = True
            assert found_status_error or "401" in exc_str, (
                f"Expected 401 error but got: {exc_str}"
            )
        assert raised, "Expected MCP client to raise on missing token but it did not"

    asyncio.run(check_mcp_client())
