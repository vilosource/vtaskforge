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


@pytest.mark.django_db
def test_update_task_depends_on_replaces_existing_links():
    """`depends_on` uses REPLACE semantics — existing depends_on links are
    dropped and recreated from the CSV list."""
    from links.models import Link
    from tests.factories import ProjectFactory

    project = ProjectFactory()
    downstream = TaskFactory(project=project, status="draft")
    old_upstream = TaskFactory(project=project)
    new_upstream_a = TaskFactory(project=project)
    new_upstream_b = TaskFactory(project=project)

    Link.objects.create(
        source_type="task", source_id=downstream.id,
        target_type="task", target_id=old_upstream.id,
        link_type="depends_on", project=project,
    )

    result = json.loads(vtf_update_task(
        task_id=downstream.id,
        depends_on=f"{new_upstream_a.id},{new_upstream_b.id}",
    ))

    assert result["success"] is True, result
    links = Link.objects.filter(source_id=downstream.id, link_type="depends_on")
    assert {l.target_id for l in links} == {new_upstream_a.id, new_upstream_b.id}


@pytest.mark.django_db
def test_update_task_depends_on_missing_target_rejects():
    """If any depends_on target is missing, no changes are persisted."""
    from links.models import Link
    from tests.factories import ProjectFactory

    project = ProjectFactory()
    downstream = TaskFactory(project=project, title="Original title")
    good = TaskFactory(project=project)
    pre_count = Link.objects.filter(source_id=downstream.id).count()

    result = json.loads(vtf_update_task(
        task_id=downstream.id, title="Should not persist",
        depends_on=f"{good.id},does_not_exist",
    ))
    assert result["success"] is False
    assert "does_not_exist" in result["message"]
    downstream.refresh_from_db()
    assert downstream.title == "Original title"
    assert Link.objects.filter(source_id=downstream.id).count() == pre_count
