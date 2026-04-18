"""Tests for the vtf_create_link MCP tool."""
import json

import pytest

from mcp_server.tools.link_create import vtf_create_link
from tests.factories import ProjectFactory, TaskFactory


@pytest.mark.django_db
def test_create_link_depends_on_task():
    """Create a depends_on Link between two tasks."""
    from links.models import Link

    project = ProjectFactory()
    upstream = TaskFactory(project=project)
    downstream = TaskFactory(project=project)

    result = json.loads(vtf_create_link(
        source_type="task", source_id=downstream.id,
        target_type="task", target_id=upstream.id,
        link_type="depends_on",
    ))

    assert result["success"] is True
    link_id = result["data"]["link"]["id"]
    link = Link.objects.get(pk=link_id)
    assert link.source_type == "task"
    assert link.source_id == downstream.id
    assert link.target_type == "task"
    assert link.target_id == upstream.id
    assert link.link_type == "depends_on"
    assert link.project_id == project.id


@pytest.mark.django_db
def test_create_link_dependent_task_is_not_claimable_until_upstream_done():
    """Integration check: depends_on gates claimability until upstream is done."""
    from links.models import Link
    from tasks.services import find_claimable_tasks

    project = ProjectFactory()
    upstream = TaskFactory(project=project, status="todo")
    downstream = TaskFactory(project=project, status="todo")

    result = json.loads(vtf_create_link(
        source_type="task", source_id=downstream.id,
        target_type="task", target_id=upstream.id,
        link_type="depends_on",
    ))
    assert result["success"] is True

    claimable_ids = {t.id for t in find_claimable_tasks(project_id=project.id)}
    assert upstream.id in claimable_ids
    assert downstream.id not in claimable_ids

    upstream.status = "done"
    upstream.save(update_fields=["status"])

    claimable_ids_after = {t.id for t in find_claimable_tasks(project_id=project.id)}
    assert downstream.id in claimable_ids_after


@pytest.mark.django_db
def test_create_link_rejects_invalid_link_type():
    project = ProjectFactory()
    task = TaskFactory(project=project)
    result = json.loads(vtf_create_link(
        source_type="task", source_id=task.id,
        target_type="task", target_id=task.id,
        link_type="not_a_real_type",
    ))
    assert result["success"] is False
    assert "not_a_real_type" in result["message"]


@pytest.mark.django_db
def test_create_link_rejects_invalid_source_type():
    project = ProjectFactory()
    task = TaskFactory(project=project)
    result = json.loads(vtf_create_link(
        source_type="bogus", source_id="x",
        target_type="task", target_id=task.id,
        link_type="depends_on",
    ))
    assert result["success"] is False
    assert "bogus" in result["message"]


@pytest.mark.django_db
def test_create_link_rejects_unknown_source_id():
    result = json.loads(vtf_create_link(
        source_type="task", source_id="does_not_exist",
        target_type="task", target_id="also_does_not_exist",
        link_type="depends_on",
    ))
    assert result["success"] is False
    assert "not found" in result["message"]


@pytest.mark.django_db
def test_create_link_rejects_malformed_metadata_json():
    project = ProjectFactory()
    task_a = TaskFactory(project=project)
    task_b = TaskFactory(project=project)
    result = json.loads(vtf_create_link(
        source_type="task", source_id=task_a.id,
        target_type="task", target_id=task_b.id,
        link_type="relates_to",
        metadata="not json at all",
    ))
    assert result["success"] is False
    assert "metadata" in result["message"].lower()


@pytest.mark.django_db
def test_create_link_accepts_valid_metadata_json():
    from links.models import Link

    project = ProjectFactory()
    task_a = TaskFactory(project=project)
    task_b = TaskFactory(project=project)
    result = json.loads(vtf_create_link(
        source_type="task", source_id=task_a.id,
        target_type="task", target_id=task_b.id,
        link_type="relates_to",
        metadata='{"note": "spike"}',
    ))
    assert result["success"] is True
    link = Link.objects.get(pk=result["data"]["link"]["id"])
    assert link.metadata == {"note": "spike"}
