"""Tests for the vtf_create_task MCP tool.

Tests call the tool Python function directly (not via MCP protocol).
"""
import json

import pytest

from mcp_server.tools.task_create import vtf_create_task
from tests.factories import ProjectFactory, TaskFactory


@pytest.mark.django_db
def test_create_task_depends_on_creates_link_rows():
    """Passing `depends_on=<task_id>` creates a Link(link_type=depends_on)."""
    from links.models import Link

    project = ProjectFactory()
    upstream_a = TaskFactory(project=project)
    upstream_b = TaskFactory(project=project)

    result = json.loads(vtf_create_task(
        title="Downstream task",
        project_id=project.id,
        depends_on=f"{upstream_a.id},{upstream_b.id}",
    ))

    assert result["success"] is True
    task_id = result["data"]["task"]["id"]

    links = Link.objects.filter(source_id=task_id, link_type="depends_on")
    assert links.count() == 2
    target_ids = set(links.values_list("target_id", flat=True))
    assert target_ids == {upstream_a.id, upstream_b.id}
    for link in links:
        assert link.source_type == "task"
        assert link.target_type == "task"
        assert link.project_id == project.id


@pytest.mark.django_db
def test_create_task_depends_on_missing_target_rejects():
    """If any depends_on target doesn't exist, reject the whole create."""
    from links.models import Link
    from tasks.models import Task

    project = ProjectFactory()
    real_upstream = TaskFactory(project=project)

    result = json.loads(vtf_create_task(
        title="Downstream",
        project_id=project.id,
        depends_on=f"{real_upstream.id},task_does_not_exist",
    ))

    assert result["success"] is False
    assert "task_does_not_exist" in result["message"]
    # No task was created, no links were created
    assert not Task.objects.filter(title="Downstream").exists()
    assert Link.objects.filter(target_id="task_does_not_exist").count() == 0


@pytest.mark.django_db
def test_create_task_without_depends_on_creates_no_links():
    """Default behavior (no depends_on param) creates zero Link rows."""
    from links.models import Link

    project = ProjectFactory()
    result = json.loads(vtf_create_task(
        title="Standalone",
        project_id=project.id,
    ))

    assert result["success"] is True
    task_id = result["data"]["task"]["id"]
    assert Link.objects.filter(source_id=task_id).count() == 0


@pytest.mark.django_db
def test_create_task_requires_is_agent_tags_not_dependencies():
    """`requires` stores tag strings on Task.requires — no Link rows are made."""
    from links.models import Link
    from tasks.models import Task

    project = ProjectFactory()
    result = json.loads(vtf_create_task(
        title="Tag-gated",
        project_id=project.id,
        requires="executor,opus",
    ))

    assert result["success"] is True
    task_id = result["data"]["task"]["id"]
    task = Task.objects.get(pk=task_id)
    assert task.requires == ["executor", "opus"]
    assert Link.objects.filter(source_id=task_id).count() == 0
