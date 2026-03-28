"""Tests for tasks.cxdb — CXDB trace lookup client."""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from tasks.cxdb import fetch_traces


MOCK_CXDB_RESPONSE = {
    "contexts": [
        {
            "context_id": 3,
            "client_tag": "cxtx/claude",
            "title": "cxtx/claude claude 2026-03-27T20:56:38Z",
            "created_at_unix_ms": 1774646196163,
            "head_turn_id": 89,
            "head_depth": 22,
            "is_live": False,
            "labels": ["cxtx", "claude", "interactive", "task:abc123"],
        },
        {
            "context_id": 5,
            "client_tag": "cxtx/claude",
            "title": "cxtx/claude rework attempt",
            "created_at_unix_ms": 1774650000000,
            "head_turn_id": 45,
            "head_depth": 11,
            "is_live": True,
            "labels": ["cxtx", "claude", "interactive", "task:abc123"],
        },
    ],
    "count": 2,
    "active_sessions": [],
    "active_tags": [],
}


@pytest.fixture(autouse=True)
def cxdb_settings(settings):
    settings.CXDB_BASE_URL = "http://cxdb-test:8080"
    settings.CXDB_WEB_URL = "https://cxdb.example.com"
    settings.CXDB_TIMEOUT_CONNECT = 1.0
    settings.CXDB_TIMEOUT_READ = 2.0


class TestFetchTraces:

    @patch("tasks.cxdb.httpx.get")
    def test_success_returns_trace_list(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CXDB_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_traces("abc123")

        assert result is not None
        assert len(result) == 2
        assert result[0]["context_id"] == 3
        assert result[0]["title"] == "cxtx/claude claude 2026-03-27T20:56:38Z"
        assert result[0]["is_live"] is False
        assert result[0]["head_depth"] == 22
        assert result[0]["created_at_unix_ms"] == 1774646196163
        assert result[0]["web_url"] == "https://cxdb.example.com/c/3"

        assert result[1]["context_id"] == 5
        assert result[1]["is_live"] is True
        assert result[1]["web_url"] == "https://cxdb.example.com/c/5"

    @patch("tasks.cxdb.httpx.get")
    def test_empty_contexts_returns_empty_list(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"contexts": [], "count": 0}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_traces("no-traces")
        assert result == []

    @patch("tasks.cxdb.httpx.get")
    def test_timeout_returns_none(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("connect timeout")

        result = fetch_traces("abc123")
        assert result is None

    @patch("tasks.cxdb.httpx.get")
    def test_connection_error_returns_none(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        result = fetch_traces("abc123")
        assert result is None

    @patch("tasks.cxdb.httpx.get")
    def test_bad_json_returns_none(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = ValueError("invalid JSON")
        mock_get.return_value = mock_response

        result = fetch_traces("abc123")
        assert result is None

    @patch("tasks.cxdb.httpx.get")
    def test_unexpected_shape_returns_none(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"not_contexts": []}
        mock_get.return_value = mock_response

        result = fetch_traces("abc123")
        assert result is None

    @patch("tasks.cxdb.httpx.get")
    def test_url_construction(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"contexts": [], "count": 0}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetch_traces("my-task-id")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "http://cxdb-test:8080/v1/contexts"
        assert call_args[1]["params"] == {"labels": "task:my-task-id", "limit": 50}

    @patch("tasks.cxdb.httpx.get")
    def test_web_url_uses_cxdb_web_url_setting(self, mock_get, settings):
        settings.CXDB_BASE_URL = "http://internal-api:8080"
        settings.CXDB_WEB_URL = "https://public-cxdb.example.com"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "contexts": [
                {
                    "context_id": 99,
                    "title": "test",
                    "is_live": False,
                    "head_depth": 5,
                    "created_at_unix_ms": 1000,
                    "labels": ["task:xyz"],
                }
            ],
            "count": 1,
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_traces("xyz")

        assert result[0]["web_url"] == "https://public-cxdb.example.com/c/99"
        assert mock_get.call_args[0][0] == "http://internal-api:8080/v1/contexts"

    @patch("tasks.cxdb.httpx.get")
    def test_http_error_status_returns_none(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        mock_get.return_value = mock_response

        result = fetch_traces("abc123")
        assert result is None
