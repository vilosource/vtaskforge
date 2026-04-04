"""Standardized v2 error response handler.

For v2 requests, normalizes all DRF exceptions into:
    {
        "error": {
            "code": "ERROR_CODE",
            "message": "Human-readable message",
            "details": {...} or null,
            "field_errors": {...} or null
        }
    }

For v1 requests, passes through the default DRF error format unchanged.
"""
from rest_framework.exceptions import (
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler as drf_exception_handler


# Map DRF exception classes to v2 error codes
_EXCEPTION_CODE_MAP = {
    ValidationError: "VALIDATION_ERROR",
    PermissionDenied: "PERMISSION_DENIED",
    NotAuthenticated: "AUTHENTICATION_REQUIRED",
    Throttled: "RATE_LIMITED",
}

# Map HTTP status codes to default error codes (fallback)
_STATUS_CODE_MAP = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_REQUIRED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "INVALID_TRANSITION",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}


def v2_exception_handler(exc, context):
    """Handle exceptions for both v1 and v2 API requests.

    v1 requests: delegate to DRF's default handler (unchanged).
    v2 requests: normalize into the standard error envelope.
    """
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    request = context.get("request")
    version = getattr(request, "version", "v1") if request else "v1"

    if version != "v2":
        return response

    # Determine error code
    code = _EXCEPTION_CODE_MAP.get(type(exc))
    if code is None:
        code = _STATUS_CODE_MAP.get(response.status_code, "UNKNOWN_ERROR")

    # Extract message
    data = response.data
    if isinstance(data, dict) and "detail" in data:
        message = str(data["detail"])
    elif isinstance(data, list):
        message = str(data[0]) if data else "An error occurred"
    elif isinstance(data, str):
        message = data
    else:
        message = str(exc)

    # Build field_errors for validation errors
    field_errors = None
    if isinstance(exc, ValidationError) and isinstance(data, dict):
        field_errors = {}
        for field, errors in data.items():
            if isinstance(errors, list):
                field_errors[field] = [str(e) for e in errors]
            else:
                field_errors[field] = [str(errors)]
        message = "Invalid input"

    # Build the standardized response
    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": None,
            "field_errors": field_errors,
        }
    }

    return response
