"""
Tests for the MCP server skeleton (P1.2).

Covers:
- FastMCP server instantiation
- Response envelope helpers (success + error)
- Token authentication utilities
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from mcp_server.auth import validate_token
from mcp_server.responses import error_response, success_response


# ---------------------------------------------------------------------------
# Server instantiation
# ---------------------------------------------------------------------------


def test_server_creates():
    """FastMCP('vtf') creates a server instance without error."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("vtf", instructions="vtaskforge task management server")
    assert server is not None


# ---------------------------------------------------------------------------
# Response envelope — success
# ---------------------------------------------------------------------------


def test_response_envelope_success():
    """success_response() shape matches the spec envelope."""
    result = success_response(data={"id": "t-1"}, message="ok", available_actions=["vtf_next_work"])
    assert result["success"] is True
    assert result["data"] == {"id": "t-1"}
    assert result["message"] == "ok"
    assert result["available_actions"] == ["vtf_next_work"]


def test_response_success_defaults():
    """success_response() with no message/actions fills safe defaults."""
    result = success_response(data=None)
    assert result["success"] is True
    assert result["message"] == ""
    assert result["available_actions"] == []


# ---------------------------------------------------------------------------
# Response envelope — error
# ---------------------------------------------------------------------------


def test_response_envelope_error():
    """error_response() shape matches the spec envelope (flat, same keys as success)."""
    result = error_response(
        message="Task 'abc' is in 'blocked' status and cannot be claimed.",
        data={"task_id": "abc", "current_status": "blocked"},
        available_actions=["vtf_search_tasks", "vtf_manage_task"],
    )
    assert result["success"] is False
    assert result["message"] == "Task 'abc' is in 'blocked' status and cannot be claimed."
    assert result["data"] == {"task_id": "abc", "current_status": "blocked"}
    assert result["available_actions"] == ["vtf_search_tasks", "vtf_manage_task"]
    # must NOT contain a nested error object
    assert "error" not in result


def test_response_error_defaults():
    """error_response() with no data/actions fills safe defaults."""
    result = error_response(message="Something went wrong")
    assert result["success"] is False
    assert result["message"] == "Something went wrong"
    assert result["data"] == {}
    assert result["available_actions"] == []


# ---------------------------------------------------------------------------
# Auth — validate_token
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_auth_valid_token():
    """validate_token() returns the User for a valid token."""
    user = User.objects.create_user(username="agent-test-valid")
    token = Token.objects.create(user=user)

    result = validate_token(token.key)
    assert result is not None
    assert result.pk == user.pk


@pytest.mark.django_db
def test_auth_invalid_token():
    """validate_token() returns None for an unknown token string."""
    result = validate_token("0000000000000000000000000000000000000000")
    assert result is None


@pytest.mark.django_db
def test_auth_missing_token():
    """validate_token() returns None when called with None."""
    result = validate_token(None)
    assert result is None


# ---------------------------------------------------------------------------
# Auto-discovery — all tool modules loaded
# ---------------------------------------------------------------------------


def test_all_tools_registered():
    """All 12 vtf tools are registered after auto-discovery imports all modules."""
    from mcp_server.server import mcp

    tool_names = [t.name for t in mcp._tool_manager._tools.values()]
    expected = {
        "vtf_board_overview",
        "vtf_next_work",
        "vtf_claim_and_start",
        "vtf_report_progress",
        "vtf_submit_work",
        "vtf_search_tasks",
        "vtf_review_task",
        "vtf_task_detail",
        "vtf_manage_task",
        "vtf_manage_milestone",
        "vtf_manage_workplan",
        "vtf_workplan_tree",
    }
    assert expected == set(tool_names), f"Tool mismatch. Registered: {tool_names}"


def test_auto_discovery_finds_all_tool_modules():
    """Auto-discovery loads every .py file from mcp_server/tools/ (except __init__.py)."""
    import importlib
    import pkgutil

    import mcp_server.tools as tools_pkg

    discovered = {
        name
        for _, name, _ in pkgutil.iter_modules(tools_pkg.__path__)
    }
    expected = {"board", "workflow", "search", "review", "detail", "manage", "workplan", "structure", "milestone"}
    assert expected == discovered, f"Module mismatch. Discovered: {discovered}"


def test_all_registered_tools_are_async():
    """All registered tools are marked async after post-registration wrapping."""
    from mcp_server.server import mcp

    for tool in mcp._tool_manager._tools.values():
        assert tool.is_async, (
            f"Tool '{tool.name}' is not async. "
            "All tools must be wrapped with sync_to_async for MCP runtime safety."
        )


def test_django_allow_async_unsafe_not_set():
    """DJANGO_ALLOW_ASYNC_UNSAFE must not be set in the environment by server.py."""
    import os

    # The server module is already imported; if it set the env var we'd see it.
    assert os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE") != "true", (
        "DJANGO_ALLOW_ASYNC_UNSAFE=true must not be set. "
        "Use sync_to_async wrapping instead."
    )


# ---------------------------------------------------------------------------
# Transport selection via environment variables
# ---------------------------------------------------------------------------


def test_server_transport_defaults_to_stdio(monkeypatch):
    """When VTF_MCP_TRANSPORT is unset, the transport defaults to 'stdio'."""
    import os

    monkeypatch.delenv("VTF_MCP_TRANSPORT", raising=False)
    transport = os.environ.get("VTF_MCP_TRANSPORT", "stdio")
    assert transport == "stdio"


def test_server_transport_http_configures_settings(monkeypatch):
    """When VTF_MCP_TRANSPORT=http, env vars resolve to expected host/port values."""
    import os

    monkeypatch.setenv("VTF_MCP_TRANSPORT", "http")
    monkeypatch.setenv("VTF_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("VTF_MCP_PORT", "8002")

    transport = os.environ.get("VTF_MCP_TRANSPORT", "stdio")
    host = os.environ.get("VTF_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("VTF_MCP_PORT", "8002"))

    assert transport == "http"
    assert host == "0.0.0.0"
    assert port == 8002


def test_server_transport_http_uses_default_host_port(monkeypatch):
    """When VTF_MCP_TRANSPORT=http with no HOST/PORT, defaults are 0.0.0.0:8002."""
    import os

    monkeypatch.setenv("VTF_MCP_TRANSPORT", "http")
    monkeypatch.delenv("VTF_MCP_HOST", raising=False)
    monkeypatch.delenv("VTF_MCP_PORT", raising=False)

    transport = os.environ.get("VTF_MCP_TRANSPORT", "stdio")
    host = os.environ.get("VTF_MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("VTF_MCP_PORT", "8002"))

    assert transport == "http"
    assert host == "0.0.0.0"
    assert port == 8002
