"""User context via contextvars.

The TokenAuthMiddleware validates the token and stores the authenticated
user in a contextvar. Tools call get_current_user() to read it.
"""

import contextvars

from django.contrib.auth.models import User

_current_user = contextvars.ContextVar("vtf_user", default=None)


def get_current_user():
    """Return the authenticated User from the current request context, or None."""
    return _current_user.get()
