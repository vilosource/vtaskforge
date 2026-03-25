"""
Async MCP HTTP client wrapper for E2E tests.

Usage:
    async with McpTestClient(url, token) as client:
        tools = await client.list_tools()
        result = await client.call_tool("vtf_board_overview")
"""
import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class McpTestClient:
    """Async context manager wrapping an MCP HTTP session.

    Opens a streamable HTTP connection and keeps it alive for the duration
    of the async with block. Each test should create its own instance so
    sessions don't bleed state.
    """

    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.token = token
        self._http_client: httpx.AsyncClient | None = None
        self._transport_cm = None
        self._session_cm = None
        self.session: ClientSession | None = None

    async def __aenter__(self) -> "McpTestClient":
        self._http_client = httpx.AsyncClient(
            headers={"Authorization": f"Token {self.token}"},
            timeout=httpx.Timeout(30.0),
        )

        # streamable_http_client is an async context manager that yields
        # (read, write, _get_session_id).  We enter it manually so we can
        # keep the connection open for the lifetime of this wrapper.
        self._transport_cm = streamable_http_client(
            url=self.url,
            http_client=self._http_client,
        )
        read, write, _ = await self._transport_cm.__aenter__()

        self._session_cm = ClientSession(read, write)
        self.session = await self._session_cm.__aenter__()
        await self.session.initialize()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(exc_type, exc_val, exc_tb)
        if self._transport_cm is not None:
            await self._transport_cm.__aexit__(exc_type, exc_val, exc_tb)
        if self._http_client is not None:
            await self._http_client.aclose()

    async def call_tool(self, name: str, **kwargs) -> dict:
        """Call an MCP tool and return the parsed JSON response body."""
        if self.session is None:
            raise RuntimeError("McpTestClient must be used as an async context manager")
        result = await self.session.call_tool(name, kwargs)
        return json.loads(result.content[0].text)

    async def list_tools(self) -> list[str]:
        """Return a sorted list of available tool names."""
        if self.session is None:
            raise RuntimeError("McpTestClient must be used as an async context manager")
        result = await self.session.list_tools()
        return sorted(t.name for t in result.tools)
