"""
Unit tests for TokenAuthMiddleware (HTTP authentication for MCP server).

Tests are standalone — they build a minimal Starlette app with the middleware
attached and use TestClient to exercise all auth paths without running the
full MCP server.

validate_token is mocked so these are pure unit tests of the middleware logic,
independent of the DB and Django test transaction boundaries.
"""
from unittest.mock import MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_server.http_auth import TokenAuthMiddleware


# ---------------------------------------------------------------------------
# Test app helpers
# ---------------------------------------------------------------------------

FAKE_TOKEN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
BAD_TOKEN = "0000000000000000000000000000000000000000"


def _ok_endpoint(request: Request):
    return JSONResponse({"ok": True})


def _build_app():
    """Return a minimal Starlette app with TokenAuthMiddleware added."""
    app = Starlette(
        routes=[
            Route("/", _ok_endpoint, methods=["GET"]),
            Route("/health", _ok_endpoint, methods=["GET"]),
            Route("/mcp", _ok_endpoint, methods=["POST"]),
        ]
    )
    app.add_middleware(TokenAuthMiddleware)
    return app


@pytest.fixture()
def client():
    """TestClient for the auth-protected Starlette app."""
    return TestClient(_build_app(), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# test_auth_valid_token
# ---------------------------------------------------------------------------


def test_auth_valid_token(client):
    """Requests with a valid token are forwarded to the endpoint (200)."""
    fake_user = MagicMock()
    fake_user.username = "agent-http-valid"

    with patch("mcp_server.http_auth.validate_token", return_value=fake_user):
        resp = client.post("/mcp", headers={"Authorization": f"Token {FAKE_TOKEN}"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ---------------------------------------------------------------------------
# test_auth_invalid_token
# ---------------------------------------------------------------------------


def test_auth_invalid_token(client):
    """Requests with an unrecognised token key return 401."""
    with patch("mcp_server.http_auth.validate_token", return_value=None):
        resp = client.post(
            "/mcp",
            headers={"Authorization": f"Token {BAD_TOKEN}"},
        )

    assert resp.status_code == 401
    body = resp.json()
    assert "error" in body


# ---------------------------------------------------------------------------
# test_auth_missing_header
# ---------------------------------------------------------------------------


def test_auth_missing_header(client):
    """Requests without an Authorization header return 401."""
    resp = client.post("/mcp")
    assert resp.status_code == 401
    body = resp.json()
    assert "error" in body


# ---------------------------------------------------------------------------
# test_auth_health_check_no_auth
# ---------------------------------------------------------------------------


def test_auth_health_check_no_auth(client):
    """GET / and GET /health pass through without any Authorization header."""
    resp_root = client.get("/")
    assert resp_root.status_code == 200

    resp_health = client.get("/health")
    assert resp_health.status_code == 200


# ---------------------------------------------------------------------------
# test_auth_wrong_format
# ---------------------------------------------------------------------------


def test_auth_wrong_format(client):
    """'Bearer <key>' format is rejected with 401 (only 'Token' scheme accepted)."""
    # Even if validate_token were to return a user, the format check fires first.
    with patch("mcp_server.http_auth.validate_token", return_value=MagicMock()):
        resp = client.post("/mcp", headers={"Authorization": f"Bearer {FAKE_TOKEN}"})

    assert resp.status_code == 401
    body = resp.json()
    assert "error" in body
