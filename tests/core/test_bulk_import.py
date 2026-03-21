"""
Tests for POST /v1/bulk/import endpoint.
"""
import pytest

from links.models import Link
from tasks.models import Task
from workplans.models import Milestone, Workplan


BULK_IMPORT_URL = "/v1/bulk/import"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def minimal_payload(**kwargs):
    """Return a minimal valid payload, optionally overriding top-level keys."""
    base = {
        "workplan": {"name": "Test Workplan", "description": "desc", "tags": ["test"]},
        "milestones": [],
        "links": [],
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_requires_authentication(unauthenticated_client):
    response = unauthenticated_client.post(BULK_IMPORT_URL, data={}, content_type="application/json")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Happy-path: workplan only
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_workplan_only(api_client):
    payload = minimal_payload()
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    data = response.json()
    assert "ref_map" in data
    assert "workplan" in data["ref_map"]
    assert "created" in data
    assert data["created"]["workplans"] == 1
    assert data["created"]["milestones"] == 0
    assert data["created"]["tasks"] == 0
    assert data["created"]["links"] == 0


@pytest.mark.django_db
def test_bulk_import_workplan_created_in_db(api_client):
    payload = minimal_payload(workplan={"name": "My WP", "description": "About it", "tags": ["a", "b"]})
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    wp_id = response.json()["ref_map"]["workplan"]
    wp = Workplan.objects.get(id=wp_id)
    assert wp.name == "My WP"
    assert wp.description == "About it"
    assert wp.tags == ["a", "b"]


# ---------------------------------------------------------------------------
# Happy-path: full import with milestones, tasks, links
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_full_payload(api_client):
    payload = {
        "workplan": {"name": "Auth rewrite", "description": "Big project", "tags": ["backend"]},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Core auth",
                "tasks": [
                    {
                        "ref": "task-1",
                        "title": "Implement JWT validation",
                        "description": "Check tokens",
                        "acceptance_criteria": ["tokens validated"],
                        "requires": ["executor"],
                    },
                    {
                        "ref": "task-2",
                        "title": "Add refresh endpoint",
                        "description": "",
                    },
                ],
            },
            {
                "ref": "phase-2",
                "name": "Session handling",
                "tasks": [
                    {"ref": "task-3", "title": "Implement sessions"},
                ],
            },
        ],
        "links": [
            {"source_ref": "task-2", "target_ref": "task-1", "type": "depends_on"},
        ],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    data = response.json()
    ref_map = data["ref_map"]

    # All refs present
    assert "workplan" in ref_map
    assert "phase-1" in ref_map
    assert "phase-2" in ref_map
    assert "task-1" in ref_map
    assert "task-2" in ref_map
    assert "task-3" in ref_map

    # Counts
    assert data["created"]["workplans"] == 1
    assert data["created"]["milestones"] == 2
    assert data["created"]["tasks"] == 3
    assert data["created"]["links"] == 1


@pytest.mark.django_db
def test_bulk_import_milestones_linked_to_workplan(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [{"ref": "phase-1", "name": "Milestone One"}],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]
    phase = Milestone.objects.get(id=ref_map["phase-1"])
    assert phase.workplan_id == ref_map["workplan"]


@pytest.mark.django_db
def test_bulk_import_tasks_linked_to_phase_and_workplan(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1", "title": "Do something"}],
            }
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]
    task = Task.objects.get(id=ref_map["task-1"])
    assert task.phase_id == ref_map["phase-1"]
    assert task.workplan_id == ref_map["workplan"]


@pytest.mark.django_db
def test_bulk_import_tasks_fields_stored_correctly(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [
                    {
                        "ref": "task-1",
                        "title": "My task",
                        "description": "Some desc",
                        "acceptance_criteria": ["crit1", "crit2"],
                        "requires": ["executor"],
                    }
                ],
            }
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]
    task = Task.objects.get(id=ref_map["task-1"])
    assert task.title == "My task"
    assert task.description == "Some desc"
    assert task.acceptance_criteria == ["crit1", "crit2"]
    assert task.requires == ["executor"]


@pytest.mark.django_db
def test_bulk_import_links_resolved_from_refs(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [
                    {"ref": "task-1", "title": "Task One"},
                    {"ref": "task-2", "title": "Task Two"},
                ],
            }
        ],
        "links": [
            {"source_ref": "task-2", "target_ref": "task-1", "type": "depends_on"},
        ],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]

    link = Link.objects.get(source_id=ref_map["task-2"])
    assert link.source_type == "task"
    assert link.target_id == ref_map["task-1"]
    assert link.target_type == "task"
    assert link.link_type == "depends_on"


@pytest.mark.django_db
def test_bulk_import_link_phase_to_task(api_client):
    """Links can reference any entity type, including phase -> task."""
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1", "title": "Task One"}],
            }
        ],
        "links": [
            {"source_ref": "task-1", "target_ref": "phase-1", "type": "relates_to"},
        ],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]
    link = Link.objects.get(source_id=ref_map["task-1"])
    assert link.target_type == "phase"
    assert link.target_id == ref_map["phase-1"]


# ---------------------------------------------------------------------------
# Ref resolution errors → 400 + rollback
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_unresolved_source_ref_returns_400(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1", "title": "Task One"}],
            }
        ],
        "links": [
            {"source_ref": "task-MISSING", "target_ref": "task-1", "type": "depends_on"},
        ],
    }
    initial_workplan_count = Workplan.objects.count()
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    # Transaction must have rolled back — nothing created
    assert Workplan.objects.count() == initial_workplan_count


@pytest.mark.django_db
def test_bulk_import_unresolved_target_ref_returns_400(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1", "title": "Task One"}],
            }
        ],
        "links": [
            {"source_ref": "task-1", "target_ref": "task-MISSING", "type": "depends_on"},
        ],
    }
    initial_workplan_count = Workplan.objects.count()
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert Workplan.objects.count() == initial_workplan_count


@pytest.mark.django_db
def test_bulk_import_transaction_rollback_on_error(api_client):
    """On any error nothing should be persisted."""
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1", "title": "Task One"}],
            }
        ],
        "links": [
            {"source_ref": "bad-ref", "target_ref": "task-1", "type": "depends_on"},
        ],
    }
    wp_before = Workplan.objects.count()
    phase_before = Milestone.objects.count()
    task_before = Task.objects.count()
    link_before = Link.objects.count()

    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400

    assert Workplan.objects.count() == wp_before
    assert Milestone.objects.count() == phase_before
    assert Task.objects.count() == task_before
    assert Link.objects.count() == link_before


# ---------------------------------------------------------------------------
# Duplicate refs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_duplicate_refs_rejected(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [
                    {"ref": "same-ref", "title": "Task One"},
                    {"ref": "same-ref", "title": "Task Two"},
                ],
            }
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Missing required fields → 400
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_missing_workplan_field(api_client):
    response = api_client.post(BULK_IMPORT_URL, data={"milestones": [], "links": []}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_bulk_import_missing_workplan_name(api_client):
    response = api_client.post(
        BULK_IMPORT_URL,
        data={"workplan": {"description": "no name"}, "milestones": [], "links": []},
        format="json",
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_bulk_import_missing_phase_ref(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [{"name": "Milestone without ref"}],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_bulk_import_missing_task_ref(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"title": "Task without ref"}],
            }
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.django_db
def test_bulk_import_missing_task_title(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1"}],
            }
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_empty_milestones_list(api_client):
    """A workplan-only import with no milestones is valid."""
    payload = {"workplan": {"name": "Solo WP"}, "milestones": [], "links": []}
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    assert Workplan.objects.filter(id=response.json()["ref_map"]["workplan"]).exists()


@pytest.mark.django_db
def test_bulk_import_phase_with_no_tasks(api_client):
    payload = {
        "workplan": {"name": "WP"},
        "milestones": [{"ref": "phase-1", "name": "Empty Milestone"}],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    assert "phase-1" in response.json()["ref_map"]


@pytest.mark.django_db
def test_bulk_import_no_milestones_key(api_client):
    """Omitting milestones key entirely is also valid."""
    payload = {"workplan": {"name": "WP"}}
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201


@pytest.mark.django_db
def test_bulk_import_workplan_ref_always_present_in_ref_map(api_client):
    payload = minimal_payload()
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]
    # The ref_map workplan value should be a nanoid string (non-empty)
    assert isinstance(ref_map["workplan"], str)
    assert len(ref_map["workplan"]) > 0
