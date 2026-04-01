"""Project context via contextvars.

The ProjectContextMiddleware extracts X-VTF-Project from HTTP headers and
stores it in a contextvar. Tools call get_default_project() to read it.
"""

import contextvars

_current_project = contextvars.ContextVar("vtf_project", default=None)


def get_default_project() -> str | None:
    """Return the project ID from the current request context, or None."""
    return _current_project.get()
