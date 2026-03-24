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
    """error_response() shape matches the spec envelope."""
    result = error_response(
        message="Task not found",
        code="not_found",
        details={"task_id": "t-99"},
    )
    assert result["success"] is False
    assert result["error"]["code"] == "not_found"
    assert result["error"]["message"] == "Task not found"
    assert result["error"]["details"] == {"task_id": "t-99"}


def test_response_error_defaults():
    """error_response() with no code/details fills safe defaults."""
    result = error_response(message="Something went wrong")
    assert result["success"] is False
    assert result["error"]["code"] == ""
    assert result["error"]["details"] == {}


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
