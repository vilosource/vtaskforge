"""Step 2: Standardized v2 error handler tests.

Tests that v2 errors are normalized to {error: {code, message, details, field_errors}}
and v1 errors pass through unchanged.
"""
import pytest
from unittest.mock import MagicMock
from rest_framework import status
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    MethodNotAllowed,
    PermissionDenied,
    Throttled,
    ValidationError,
)


def _make_context(version="v2"):
    """Build a mock context dict with request.version set."""
    request = MagicMock()
    request.version = version
    return {"request": request, "view": MagicMock()}


class TestV2ExceptionHandler:
    """DoD #5-13: v2 error handler normalizes all errors."""

    def test_error_v2_validation_error(self):
        """DoD #5: ValidationError -> VALIDATION_ERROR with field_errors."""
        from core.exception_handler import v2_exception_handler

        exc = ValidationError({"title": ["This field may not be blank."]})
        response = v2_exception_handler(exc, _make_context("v2"))
        assert response.status_code == 400
        body = response.data
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "title" in body["error"]["field_errors"]

    def test_error_v2_permission_denied(self):
        """DoD #6: PermissionDenied -> PERMISSION_DENIED."""
        from core.exception_handler import v2_exception_handler

        exc = PermissionDenied("Not allowed")
        response = v2_exception_handler(exc, _make_context("v2"))
        assert response.status_code == 403
        assert response.data["error"]["code"] == "PERMISSION_DENIED"

    def test_error_v2_not_found(self):
        """DoD #7: NotFound -> NOT_FOUND."""
        from core.exception_handler import v2_exception_handler

        exc = NotFound("No such resource")
        response = v2_exception_handler(exc, _make_context("v2"))
        assert response.status_code == 404
        assert response.data["error"]["code"] == "NOT_FOUND"

    def test_error_v2_authentication_required(self):
        """DoD #8: NotAuthenticated -> AUTHENTICATION_REQUIRED."""
        from core.exception_handler import v2_exception_handler

        exc = NotAuthenticated()
        response = v2_exception_handler(exc, _make_context("v2"))
        assert response.status_code == 401
        assert response.data["error"]["code"] == "AUTHENTICATION_REQUIRED"

    def test_error_v2_method_not_allowed(self):
        """DoD #9: MethodNotAllowed -> METHOD_NOT_ALLOWED."""
        from core.exception_handler import v2_exception_handler

        exc = MethodNotAllowed("PUT")
        response = v2_exception_handler(exc, _make_context("v2"))
        assert response.status_code == 405
        assert response.data["error"]["code"] == "METHOD_NOT_ALLOWED"

    def test_error_v2_throttled(self):
        """DoD #10: Throttled -> RATE_LIMITED."""
        from core.exception_handler import v2_exception_handler

        exc = Throttled(wait=30)
        response = v2_exception_handler(exc, _make_context("v2"))
        assert response.status_code == 429
        assert response.data["error"]["code"] == "RATE_LIMITED"

    def test_error_v1_unchanged(self):
        """DoD #11: v1 errors pass through in original DRF format."""
        from core.exception_handler import v2_exception_handler

        exc = NotFound("No such resource")
        response = v2_exception_handler(exc, _make_context("v1"))
        assert response.status_code == 404
        # v1 format: {"detail": "..."} — NOT wrapped in {error: {...}}
        assert "error" not in response.data
        assert "detail" in response.data

    def test_error_v2_field_errors_structure(self):
        """DoD #12: Nested validation -> field_errors dict."""
        from core.exception_handler import v2_exception_handler

        exc = ValidationError({
            "title": ["Required."],
            "project": ["Not found."],
        })
        response = v2_exception_handler(exc, _make_context("v2"))
        fe = response.data["error"]["field_errors"]
        assert "title" in fe
        assert "project" in fe

    def test_error_v2_details_null_when_absent(self):
        """DoD #13: Non-validation errors have details=null, field_errors=null."""
        from core.exception_handler import v2_exception_handler

        exc = NotFound("Gone")
        response = v2_exception_handler(exc, _make_context("v2"))
        assert response.data["error"]["details"] is None
        assert response.data["error"]["field_errors"] is None
