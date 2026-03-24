"""
Tests for the vtf_board_overview MCP tool (P1.3).

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.board import vtf_board_overview
from tests.factories import ProjectFactory, TaskFactory


# ---------------------------------------------------------------------------
# test_board_overview_returns_counts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_board_overview_returns_counts():
    """Board overview returns counts for each status present in the data."""
    project = ProjectFactory()
    TaskFactory(project=project, status="todo")
    TaskFactory(project=project, status="todo")
    TaskFactory(project=project, status="doing")
    TaskFactory(project=project, status="done")

    result = json.loads(vtf_board_overview(project_id=project.id))

    assert result["success"] is True
    counts = result["data"]["counts"]
    assert counts.get("todo") == 2
    assert counts.get("doing") == 1
    assert counts.get("done") == 1


# ---------------------------------------------------------------------------
# test_board_overview_includes_attention_items
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_board_overview_includes_attention_items():
    """Board overview attention_items includes blocked and needs_attention tasks."""
    project = ProjectFactory()
    blocked_task = TaskFactory(project=project, status="blocked")
    attention_task = TaskFactory(project=project, status="needs_attention")
    TaskFactory(project=project, status="todo")  # should NOT appear

    result = json.loads(vtf_board_overview(project_id=project.id))

    assert result["success"] is True
    attention_items = result["data"]["attention_items"]
    attention_ids = {item["id"] for item in attention_items}
    assert blocked_task.id in attention_ids
    assert attention_task.id in attention_ids
    # todo task must not appear
    assert len(attention_items) == 2


# ---------------------------------------------------------------------------
# test_board_overview_includes_pending_reviews
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_board_overview_includes_pending_reviews():
    """Board overview pending_reviews includes tasks in pending review statuses."""
    project = ProjectFactory()
    completion_review = TaskFactory(project=project, status="pending_completion_review")
    start_review = TaskFactory(project=project, status="pending_start_review")
    TaskFactory(project=project, status="todo")  # should NOT appear

    result = json.loads(vtf_board_overview(project_id=project.id))

    assert result["success"] is True
    pending_reviews = result["data"]["pending_reviews"]
    pending_ids = {item["id"] for item in pending_reviews}
    assert completion_review.id in pending_ids
    assert start_review.id in pending_ids
    assert len(pending_reviews) == 2


# ---------------------------------------------------------------------------
# test_board_overview_with_project_filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_board_overview_with_project_filter():
    """Board overview filtered by project_id returns only that project's tasks."""
    project_a = ProjectFactory()
    project_b = ProjectFactory()

    TaskFactory(project=project_a, status="todo")
    TaskFactory(project=project_a, status="done")
    TaskFactory(project=project_b, status="todo")
    TaskFactory(project=project_b, status="doing")
    TaskFactory(project=project_b, status="doing")

    result_a = json.loads(vtf_board_overview(project_id=project_a.id))
    counts_a = result_a["data"]["counts"]
    assert counts_a.get("todo") == 1
    assert counts_a.get("done") == 1
    assert "doing" not in counts_a

    result_b = json.loads(vtf_board_overview(project_id=project_b.id))
    counts_b = result_b["data"]["counts"]
    assert counts_b.get("todo") == 1
    assert counts_b.get("doing") == 2


# ---------------------------------------------------------------------------
# test_board_overview_empty_project
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_board_overview_empty_project():
    """Board overview for a project with no tasks returns clean empty response."""
    project = ProjectFactory()

    result = json.loads(vtf_board_overview(project_id=project.id))

    assert result["success"] is True
    data = result["data"]
    assert data["counts"] == {}
    assert data["attention_items"] == []
    assert data["pending_reviews"] == []
    assert data["active_agents"] == []


# ---------------------------------------------------------------------------
# test_board_overview_response_envelope
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_board_overview_response_envelope():
    """Board overview response has correct success envelope with data key."""
    result = json.loads(vtf_board_overview())

    assert result["success"] is True
    assert "data" in result
    assert "message" in result
    assert "available_actions" in result

    data = result["data"]
    assert "counts" in data
    assert "attention_items" in data
    assert "pending_reviews" in data
    assert "active_agents" in data
