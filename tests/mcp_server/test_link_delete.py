"""Tests for the vtf_delete_link MCP tool."""
import json

import pytest

from mcp_server.tools.link_delete import vtf_delete_link
from mcp_server.user_context import _current_user
from tests.factories import ProjectFactory, TaskFactory


@pytest.fixture(autouse=True)
def staff_user_context(db):
    from django.contrib.auth.models import User
    user = User.objects.create_user("mcp-staff", password="x", is_staff=True)
    token = _current_user.set(user)
    yield user
    _current_user.reset(token)


@pytest.mark.django_db
def test_delete_link_removes_row():
    from links.models import Link

    project = ProjectFactory()
    a = TaskFactory(project=project)
    b = TaskFactory(project=project)
    link = Link.objects.create(
        source_type="task", source_id=a.id,
        target_type="task", target_id=b.id,
        link_type="depends_on", project=project,
    )

    result = json.loads(vtf_delete_link(link_id=link.id))

    assert result["success"] is True
    assert not Link.objects.filter(pk=link.id).exists()


@pytest.mark.django_db
def test_delete_link_missing_id_rejected():
    result = json.loads(vtf_delete_link(link_id=""))
    assert result["success"] is False
    assert "required" in result["message"].lower()


@pytest.mark.django_db
def test_delete_link_unknown_id_returns_not_found():
    result = json.loads(vtf_delete_link(link_id="missing_link_xyz"))
    assert result["success"] is False
    assert "not found" in result["message"].lower()


@pytest.mark.django_db
def test_delete_link_rejects_non_member():
    from django.contrib.auth.models import User
    from links.models import Link

    project = ProjectFactory()
    a = TaskFactory(project=project)
    b = TaskFactory(project=project)
    link = Link.objects.create(
        source_type="task", source_id=a.id,
        target_type="task", target_id=b.id,
        link_type="depends_on", project=project,
    )

    outsider = User.objects.create_user("outsider", password="x")
    tok = _current_user.set(outsider)
    try:
        result = json.loads(vtf_delete_link(link_id=link.id))
    finally:
        _current_user.reset(tok)

    assert result["success"] is False
    assert "not a member" in result["message"].lower()
    assert Link.objects.filter(pk=link.id).exists()  # Not deleted
