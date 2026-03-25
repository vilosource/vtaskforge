"""
HTTP authentication middleware for the MCP server's HTTP (streamable-HTTP) transport.

Validates Authorization: Token <key> headers against Django's authtoken table.
Health check endpoints (GET / and GET /health) are exempt from authentication.
Stdio transport is unaffected — this middleware is only applied when the server
runs in HTTP mode.
"""
from asgiref.sync import sync_to_async
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_server.auth import validate_token

# Paths that bypass authentication entirely.
HEALTH_PATHS = {"/", "/health"}


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces token authentication for the MCP HTTP transport.

    - Accepts requests where Authorization header is "Token <key>" and the key is valid.
    - Returns 401 JSON for missing, malformed, or invalid tokens.
    - Health check paths (GET / and GET /health) pass through unauthenticated.
    """

    async def dispatch(self, request: Request, call_next):
        # Health checks bypass auth.
        if request.method == "GET" and request.url.path in HEALTH_PATHS:
            return await call_next(request)

        # Extract and validate the token.
        auth_header = request.headers.get("Authorization", "")
        token = _extract_token(auth_header)

        if token is None:
            return JSONResponse(
                {"error": "Authentication required. Provide Authorization: Token <key>"},
                status_code=401,
            )

        user = await sync_to_async(validate_token)(token)
        if user is None:
            return JSONResponse(
                {"error": "Invalid or expired token."},
                status_code=401,
            )

        return await call_next(request)


def _extract_token(auth_header: str):
    """
    Parse the Authorization header and return the token string.

    Accepts "Token <key>" format only. Returns None if malformed or absent.
    """
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Token":
        return None
    token = parts[1].strip()
    return token if token else None
