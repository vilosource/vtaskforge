"""Shared input parsing utilities for MCP tools.

Centralizes all field parsing logic that was previously duplicated
across 8+ tool files: comma-separated lists, booleans, JSON-or-CSV,
test commands.
"""
import json


def parse_csv_list(value: str | None) -> list[str]:
    """Parse comma-separated string into list of stripped, non-empty strings."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_bool(value: str | bool | None) -> bool | None:
    """Parse a string boolean value.

    Returns None for None input (distinguishes "not provided" from "false").
    Accepts: true/false, yes/no, 1/0, True/False.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("true", "1", "yes")


def parse_json_or_csv(value: str | None) -> list[str]:
    """Parse a value as JSON array or fall back to comma-separated list.

    Used for acceptance_criteria, requires, and similar fields that
    accept either JSON arrays or comma-separated strings.
    """
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return parse_csv_list(value)


def parse_test_command(value: str | None) -> dict:
    """Parse test command as JSON dict or wrap plain string.

    Returns:
        {} for empty/None
        Parsed dict for valid JSON object
        {"command": value} for plain string
    """
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {"command": value}
