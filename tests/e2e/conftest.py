"""
E2E test fixtures.

The E2E stack (docker-compose.e2e.yml) must already be running and seeded
before pytest is invoked.  These fixtures do NOT manage the stack lifecycle —
that is the responsibility of scripts/run-e2e.sh (P6.6).

If the stack is not up, fixtures fail fast with a clear error message.

Ports:
  - API:  http://localhost:18000/v1
  - MCP:  http://localhost:18002/mcp

Known token (set by seed.py): e2e-test-token-12345
"""
import asyncio
import time

import httpx
import pytest

from tests.e2e.mcp_client import McpTestClient
from tests.e2e.rest_client import RestTestClient

# ---------------------------------------------------------------------------
# Constants — match seed.py and docker-compose.e2e.yml
# ---------------------------------------------------------------------------

E2E_API_URL = "http://localhost:18000/v1"
E2E_MCP_URL = "http://localhost:18002/mcp"
E2E_AUTH_TOKEN = "e2e-test-token-12345"

# ---------------------------------------------------------------------------
# Stack readiness check
# ---------------------------------------------------------------------------


def _check_api_ready(url: str, timeout: float = 10.0) -> bool:
    """Return True if the REST API responds within timeout.

    Uses the /tasks/ endpoint (auth required) rather than /health to avoid
    the 3-second Redis connection timeout in the health check view.
    The E2E stack has no Redis; /tasks/ responds immediately once Django + DB are up.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(
                f"{url}/tasks/",
                headers={"Authorization": f"Token {E2E_AUTH_TOKEN}"},
                timeout=3.0,
            )
            if r.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadTimeout):
            time.sleep(0.5)
    return False


def _check_mcp_ready(url: str, timeout: float = 5.0) -> bool:
    """Return True if the MCP server port responds within timeout.

    The MCP server doesn't have a plain HTTP health path, but we can confirm
    the TCP port accepts connections via a quick GET probe.  A 4xx response
    still means the server is up.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            # Any HTTP response (200, 404, 405, 400) means the server is up.
            if r.status_code < 600:
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_api_url() -> str:
    """URL for the E2E REST API (includes /v1 prefix)."""
    if not _check_api_ready(E2E_API_URL):
        pytest.fail(
            "E2E API is not responding at %s — "
            "start the stack first: "
            "docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait"
            % E2E_API_URL
        )
    return E2E_API_URL


@pytest.fixture(scope="session")
def e2e_mcp_url() -> str:
    """URL for the E2E MCP server."""
    if not _check_mcp_ready(E2E_MCP_URL):
        pytest.fail(
            "E2E MCP server is not responding at %s — "
            "start the stack first: "
            "docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait"
            % E2E_MCP_URL
        )
    return E2E_MCP_URL


@pytest.fixture(scope="session")
def auth_token() -> str:
    """Known DRF token created by seed.py."""
    return E2E_AUTH_TOKEN


@pytest.fixture(scope="session")
def rest_client(e2e_api_url, auth_token) -> RestTestClient:
    """Session-scoped REST client.  Shared across all tests in the session."""
    client = RestTestClient(base_url=e2e_api_url, token=auth_token)
    yield client
    client.close()


# ---------------------------------------------------------------------------
# Function-scoped MCP client factory
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp_client(e2e_mcp_url, auth_token):
    """Factory fixture — yields a connected McpTestClient for one test.

    Each test gets its own MCP session so state doesn't leak between tests.
    The client is torn down after the test completes.
    """

    async def _run_with_client(coro_fn):
        async with McpTestClient(url=e2e_mcp_url, token=auth_token) as client:
            return await coro_fn(client)

    # Return the runner so tests can do:
    #   def test_foo(mcp_client):
    #       result = mcp_client(lambda c: c.call_tool("vtf_board_overview"))
    # OR tests can use the async context manager directly via asyncio.run().
    return McpTestClient(url=e2e_mcp_url, token=auth_token)


# ---------------------------------------------------------------------------
# Convenience fixture: pre-fetched tool list (session-scoped)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mcp_tools(e2e_mcp_url, auth_token) -> list[str]:
    """Return the sorted list of tool names registered on the MCP server."""

    async def _get_tools():
        async with McpTestClient(url=e2e_mcp_url, token=auth_token) as client:
            return await client.list_tools()

    return asyncio.run(_get_tools())
