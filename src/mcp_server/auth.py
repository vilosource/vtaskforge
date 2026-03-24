"""
MCP Server authentication utilities.

Validates agent tokens against the Django authtoken table.
Tokens are the same tokens issued at agent registration via POST /v1/agents/.
"""
import os
from typing import Optional

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


def validate_token(token: Optional[str]) -> Optional[User]:
    """
    Validate a token string against the Django authtoken table.

    Returns the associated User if valid, None if invalid or not found.
    """
    if not token:
        return None
    try:
        tok = Token.objects.select_related("user").get(key=token)
        return tok.user
    except Token.DoesNotExist:
        return None


def get_token_from_env() -> Optional[str]:
    """
    Read the VTF_TOKEN environment variable.

    Returns the token string or None if not set.
    """
    return os.environ.get("VTF_TOKEN") or None
