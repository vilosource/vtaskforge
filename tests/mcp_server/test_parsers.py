"""Tests for MCP input parsing utilities."""
import json
import pytest


class TestParseCsvList:

    def test_basic_split(self):
        from mcp_server.parsers import parse_csv_list
        assert parse_csv_list("a,b,c") == ["a", "b", "c"]

    def test_strips_whitespace(self):
        from mcp_server.parsers import parse_csv_list
        assert parse_csv_list(" a , b , c ") == ["a", "b", "c"]

    def test_empty_string(self):
        from mcp_server.parsers import parse_csv_list
        assert parse_csv_list("") == []

    def test_none(self):
        from mcp_server.parsers import parse_csv_list
        assert parse_csv_list(None) == []

    def test_filters_empty_items(self):
        from mcp_server.parsers import parse_csv_list
        assert parse_csv_list("a,,b,") == ["a", "b"]


class TestParseBool:

    def test_true_values(self):
        from mcp_server.parsers import parse_bool
        for v in ("true", "True", "TRUE", "1", "yes", "Yes"):
            assert parse_bool(v) is True

    def test_false_values(self):
        from mcp_server.parsers import parse_bool
        for v in ("false", "False", "FALSE", "0", "no", "No"):
            assert parse_bool(v) is False

    def test_none(self):
        from mcp_server.parsers import parse_bool
        assert parse_bool(None) is None

    def test_empty_string_returns_none(self):
        """Empty string means 'not provided' — callers distinguish via `is not None`."""
        from mcp_server.parsers import parse_bool
        assert parse_bool("") is None

    def test_already_bool(self):
        from mcp_server.parsers import parse_bool
        assert parse_bool(True) is True
        assert parse_bool(False) is False


class TestParseJsonOrCsv:

    def test_json_array(self):
        from mcp_server.parsers import parse_json_or_csv
        assert parse_json_or_csv('["a", "b"]') == ["a", "b"]

    def test_csv_fallback(self):
        from mcp_server.parsers import parse_json_or_csv
        assert parse_json_or_csv("a, b, c") == ["a", "b", "c"]

    def test_empty(self):
        from mcp_server.parsers import parse_json_or_csv
        assert parse_json_or_csv("") == []


class TestParseTestCommand:

    def test_json_dict(self):
        from mcp_server.parsers import parse_test_command
        result = parse_test_command('{"unit": "pytest tests/"}')
        assert result == {"unit": "pytest tests/"}

    def test_plain_string(self):
        from mcp_server.parsers import parse_test_command
        result = parse_test_command("pytest tests/")
        assert result == {"command": "pytest tests/"}

    def test_empty(self):
        from mcp_server.parsers import parse_test_command
        assert parse_test_command("") == {}

    def test_none(self):
        from mcp_server.parsers import parse_test_command
        assert parse_test_command(None) == {}
