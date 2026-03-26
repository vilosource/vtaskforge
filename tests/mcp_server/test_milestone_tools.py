"""
Tests for the vtf_manage_milestone MCP tool.

Covers: create, list ordered, update order, activate, complete, delete,
invalid transitions (complete from pending), missing workplan_id.
"""
import json

import pytest

from projects.models import Project
from workplans.models import Milestone, Workplan


@pytest.fixture
def project(db):
    return Project.objects.create(name="test-project", id="msp-proj")


@pytest.fixture
def workplan(project):
    return Workplan.objects.create(name="test-workplan", project=project, status="active")


@pytest.fixture
def pending_milestone(workplan):
    return Milestone.objects.create(name="Milestone A", workplan=workplan, order=0)


@pytest.fixture
def active_milestone(workplan):
    m = Milestone.objects.create(name="Milestone B", workplan=workplan, order=1)
    m.status = "active"
    m.save()
    return m


# ---------------------------------------------------------------------------
# AC1: create milestone under workplan with correct order
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_milestone_basic(workplan):
    """Create a milestone under a workplan with a name and order."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(
            action="create",
            workplan_id=workplan.id,
            name="Sprint 1",
            order="2",
        )
    )

    assert result["success"] is True
    m = result["data"]["milestone"]
    assert m["name"] == "Sprint 1"
    assert m["order"] == 2
    assert m["status"] == "pending"
    assert m["workplan_id"] == workplan.id


@pytest.mark.django_db
def test_create_milestone_default_order(workplan):
    """Create milestone with no order defaults to 0."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(action="create", workplan_id=workplan.id, name="Default Order")
    )

    assert result["success"] is True
    assert result["data"]["milestone"]["order"] == 0


@pytest.mark.django_db
def test_create_milestone_requires_name(workplan):
    """Create without name returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(action="create", workplan_id=workplan.id)
    )
    assert result["success"] is False
    assert "name" in result["message"]


@pytest.mark.django_db
def test_create_milestone_requires_workplan_id():
    """Create without workplan_id returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(vtf_manage_milestone(action="create", name="Orphan"))
    assert result["success"] is False
    assert "workplan_id" in result["message"]


@pytest.mark.django_db
def test_create_milestone_nonexistent_workplan():
    """Create with non-existent workplan_id returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(action="create", workplan_id="no-such-wp", name="X")
    )
    assert result["success"] is False
    assert "not found" in result["message"]


# ---------------------------------------------------------------------------
# AC2: list returns milestones ordered by `order` field with task counts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_milestones_ordered(workplan):
    """List returns milestones in order field order with task counts."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    Milestone.objects.create(name="Z Last", workplan=workplan, order=10)
    Milestone.objects.create(name="A First", workplan=workplan, order=1)
    Milestone.objects.create(name="M Mid", workplan=workplan, order=5)

    result = json.loads(
        vtf_manage_milestone(action="list", workplan_id=workplan.id)
    )

    assert result["success"] is True
    milestones = result["data"]["milestones"]
    assert len(milestones) == 3
    orders = [m["order"] for m in milestones]
    assert orders == sorted(orders), "Milestones should be returned in ascending order"


@pytest.mark.django_db
def test_list_milestones_includes_task_counts(workplan):
    """List includes task_counts dict for each milestone."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    Milestone.objects.create(name="Empty", workplan=workplan, order=0)

    result = json.loads(
        vtf_manage_milestone(action="list", workplan_id=workplan.id)
    )

    assert result["success"] is True
    m = result["data"]["milestones"][0]
    assert "task_counts" in m


@pytest.mark.django_db
def test_list_milestones_requires_workplan_id():
    """List without workplan_id returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(vtf_manage_milestone(action="list"))
    assert result["success"] is False
    assert "workplan_id" in result["message"]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_milestone_order(pending_milestone):
    """Update can change order."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(
            action="update",
            milestone_id=pending_milestone.id,
            order="99",
        )
    )

    assert result["success"] is True
    pending_milestone.refresh_from_db()
    assert pending_milestone.order == 99


@pytest.mark.django_db
def test_update_milestone_name_and_description(pending_milestone):
    """Update can change name and description."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(
            action="update",
            milestone_id=pending_milestone.id,
            name="New Name",
            description="A description",
        )
    )

    assert result["success"] is True
    pending_milestone.refresh_from_db()
    assert pending_milestone.name == "New Name"
    assert pending_milestone.description == "A description"


@pytest.mark.django_db
def test_update_milestone_requires_milestone_id():
    """Update without milestone_id returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(vtf_manage_milestone(action="update", name="X"))
    assert result["success"] is False
    assert "milestone_id" in result["message"]


# ---------------------------------------------------------------------------
# AC3: activate transitions pending → active
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_activate_milestone(pending_milestone):
    """Activate transitions a pending milestone to active."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(action="activate", milestone_id=pending_milestone.id)
    )

    assert result["success"] is True
    pending_milestone.refresh_from_db()
    assert pending_milestone.status == "active"


@pytest.mark.django_db
def test_activate_requires_milestone_id():
    """Activate without milestone_id returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(vtf_manage_milestone(action="activate"))
    assert result["success"] is False
    assert "milestone_id" in result["message"]


# ---------------------------------------------------------------------------
# AC4: complete transitions active → completed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_complete_milestone(active_milestone):
    """Complete transitions an active milestone to completed."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(action="complete", milestone_id=active_milestone.id)
    )

    assert result["success"] is True
    active_milestone.refresh_from_db()
    assert active_milestone.status == "completed"


@pytest.mark.django_db
def test_complete_requires_milestone_id():
    """Complete without milestone_id returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(vtf_manage_milestone(action="complete"))
    assert result["success"] is False
    assert "milestone_id" in result["message"]


# ---------------------------------------------------------------------------
# AC5: Invalid transitions return helpful error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_complete_from_pending_is_invalid(pending_milestone):
    """Completing a pending milestone (not active) returns a helpful error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(action="complete", milestone_id=pending_milestone.id)
    )

    assert result["success"] is False
    assert "active" in result["message"].lower() or "pending" in result["message"].lower()


@pytest.mark.django_db
def test_activate_already_active_is_invalid(active_milestone):
    """Activating an already-active milestone returns a helpful error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(
        vtf_manage_milestone(action="activate", milestone_id=active_milestone.id)
    )

    assert result["success"] is False
    assert "pending" in result["message"].lower() or "active" in result["message"].lower()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_delete_milestone(pending_milestone):
    """Delete removes the milestone."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    m_id = pending_milestone.id
    result = json.loads(
        vtf_manage_milestone(action="delete", milestone_id=m_id)
    )

    assert result["success"] is True
    assert not Milestone.objects.filter(pk=m_id).exists()


@pytest.mark.django_db
def test_delete_requires_milestone_id():
    """Delete without milestone_id returns error."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(vtf_manage_milestone(action="delete"))
    assert result["success"] is False
    assert "milestone_id" in result["message"]


# ---------------------------------------------------------------------------
# Unknown action
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unknown_action():
    """Unknown action returns error with suggestion."""
    from mcp_server.tools.milestone import vtf_manage_milestone

    result = json.loads(vtf_manage_milestone(action="frobnicate"))
    assert result["success"] is False
    assert "frobnicate" in result["message"]
