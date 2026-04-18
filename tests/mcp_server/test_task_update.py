"""Tests for the vtf_update_task MCP tool.

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.task_update import vtf_update_task
from tests.factories import TaskFactory


@pytest.mark.django_db
def test_update_task_unspecified_booleans_are_preserved():
    """Unspecified boolean params must not clobber existing task fields.

    Regression: previously `parse_bool("")` returned `False`, so the
    `if val is not None` guard let empty-string defaults silently reset
    every boolean field to False on any partial update.
    """
    task = TaskFactory(
        status="draft",
        judge=True,
        needs_review_before_start=True,
        needs_review_on_completion=True,
    )

    result = json.loads(vtf_update_task(task_id=task.id, labels="a,b"))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.judge is True
    assert task.needs_review_before_start is True
    assert task.needs_review_on_completion is True
    assert task.labels == ["a", "b"]


@pytest.mark.django_db
def test_update_task_explicit_false_still_applies():
    """Explicit `judge="false"` must still set the field to False."""
    task = TaskFactory(status="draft", judge=True)

    result = json.loads(vtf_update_task(task_id=task.id, judge="false"))

    assert result["success"] is True
    task.refresh_from_db()
    assert task.judge is False
