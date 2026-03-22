"""
Tests for POST /v1/bulk/import endpoint.
"""
import pytest

from links.models import Link
from tasks.models import Task
from workplans.models import Milestone, Workplan
from projects.models import Project


BULK_IMPORT_URL = "/v1/bulk/import"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def minimal_payload(**kwargs):
    """Return a minimal valid payload, optionally overriding top-level keys."""
    base = {
        "project": {"name": "Test Project", "description": "A test project", "tags": ["test"]},
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
        "project": {"name": "Auth Project", "description": "Authentication project", "tags": ["auth"]},
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
        "project": {"name": "Test Project"},
        "workplan": {"name": "WP"},
        "milestones": [{"ref": "phase-1", "name": "Milestone One"}],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]
    milestone = Milestone.objects.get(id=ref_map["phase-1"])
    assert milestone.workplan_id == ref_map["workplan"]


@pytest.mark.django_db
def test_bulk_import_tasks_linked_to_phase_and_workplan(api_client):
    payload = {
        "project": {"name": "Test Project"},
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
    assert task.milestone_id == ref_map["phase-1"]
    assert task.workplan_id == ref_map["workplan"]


@pytest.mark.django_db
def test_bulk_import_tasks_fields_stored_correctly(api_client):
    payload = {
        "project": {"name": "Test Project"},
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
        "project": {"name": "Test Project"},
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
    """Links can reference any entity type, including milestone -> task."""
    payload = {
        "project": {"name": "Test Project"},
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
    assert link.target_type == "milestone"
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
    payload = {"project": {"name": "Test Project"}, "workplan": {"name": "Solo WP"}, "milestones": [], "links": []}
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    assert Workplan.objects.filter(id=response.json()["ref_map"]["workplan"]).exists()


@pytest.mark.django_db
def test_bulk_import_phase_with_no_tasks(api_client):
    payload = {
        "project": {"name": "Test Project"},
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
    payload = {"project": {"name": "Test Project"}, "workplan": {"name": "WP"}}
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


# ---------------------------------------------------------------------------
# Project context tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_missing_project_returns_400(api_client):
    """Missing both project_id and project should return 400."""
    payload = {
        "workplan": {"name": "Test Workplan"},
        "milestones": [],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "project_id or project is required" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_bulk_import_project_id_sets_project_on_tasks(api_client):
    """When project_id is provided, all tasks get that project."""
    from tests.factories import ProjectFactory
    project = ProjectFactory()
    payload = {
        "project_id": project.id,
        "workplan": {"name": "Test Workplan"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1", "title": "Test Task"}],
            }
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]
    task = Task.objects.get(id=ref_map["task-1"])
    assert task.project_id == project.id


# ---------------------------------------------------------------------------
# backlog_tasks tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_backlog_tasks_creates_tasks_with_null_milestone(api_client):
    """backlog_tasks section creates tasks with null milestone."""
    payload = {
        "project": {"name": "Test Project"},
        "workplan": {"name": "Test Workplan"},
        "milestones": [],
        "backlog_tasks": [
            {"ref": "backlog-1", "title": "Backlog Task 1"},
            {"ref": "backlog-2", "title": "Backlog Task 2"},
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]

    # Both backlog tasks created
    assert "backlog-1" in ref_map
    assert "backlog-2" in ref_map

    # Tasks have null milestone but correct project/workplan
    task1 = Task.objects.get(id=ref_map["backlog-1"])
    task2 = Task.objects.get(id=ref_map["backlog-2"])

    assert task1.milestone is None
    assert task2.milestone is None
    assert task1.workplan_id == ref_map["workplan"]
    assert task2.workplan_id == ref_map["workplan"]


@pytest.mark.django_db
def test_bulk_import_backlog_tasks_with_workplan_id(api_client):
    """backlog_tasks get the workplan when workplan_id is provided."""
    from tests.factories import ProjectFactory, WorkplanFactory
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)
    payload = {
        "project_id": project.id,
        "workplan_id": workplan.id,
        "milestones": [],
        "backlog_tasks": [
            {"ref": "backlog-1", "title": "Backlog Task"},
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]

    task = Task.objects.get(id=ref_map["backlog-1"])
    assert task.milestone is None
    assert task.workplan_id == workplan.id
    assert task.project_id == project.id


@pytest.mark.django_db
def test_bulk_import_links_between_milestone_tasks_and_backlog_tasks(api_client):
    """Links can connect milestone tasks and backlog tasks."""
    payload = {
        "project": {"name": "Test Project"},
        "workplan": {"name": "Test Workplan"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [{"ref": "task-1", "title": "Milestone Task"}],
            }
        ],
        "backlog_tasks": [
            {"ref": "backlog-1", "title": "Backlog Task"},
        ],
        "links": [
            {"source_ref": "backlog-1", "target_ref": "task-1", "type": "depends_on"},
        ],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    ref_map = response.json()["ref_map"]

    # Link created correctly
    link = Link.objects.get(source_id=ref_map["backlog-1"])
    assert link.source_type == "task"
    assert link.target_id == ref_map["task-1"]
    assert link.target_type == "task"
    assert link.link_type == "depends_on"


@pytest.mark.django_db
def test_bulk_import_backlog_tasks_validation(api_client):
    """backlog_tasks must have required fields."""
    payload = {
        "project": {"name": "Test Project"},
        "workplan": {"name": "Test Workplan"},
        "milestones": [],
        "backlog_tasks": [
            {"title": "Missing ref"},  # No ref
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "backlog_tasks[0].ref is required" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_bulk_import_backlog_tasks_missing_title(api_client):
    """backlog_tasks must have title."""
    payload = {
        "project": {"name": "Test Project"},
        "workplan": {"name": "Test Workplan"},
        "milestones": [],
        "backlog_tasks": [
            {"ref": "backlog-1"},  # No title
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "backlog_tasks[0].title is required" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_bulk_import_task_count_includes_backlog_tasks(api_client):
    """Response task count includes both milestone tasks and backlog tasks."""
    payload = {
        "project": {"name": "Test Project"},
        "workplan": {"name": "Test Workplan"},
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Milestone One",
                "tasks": [
                    {"ref": "task-1", "title": "Milestone Task 1"},
                    {"ref": "task-2", "title": "Milestone Task 2"},
                ],
            }
        ],
        "backlog_tasks": [
            {"ref": "backlog-1", "title": "Backlog Task 1"},
            {"ref": "backlog-2", "title": "Backlog Task 2"},
            {"ref": "backlog-3", "title": "Backlog Task 3"},
        ],
        "links": [],
    }
    response = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["created"]["milestones"] == 1
    assert data["created"]["tasks"] == 5  # 2 milestone + 3 backlog


# ---------------------------------------------------------------------------
# Re-import tests (milestone deduplication)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bulk_import_reuses_existing_milestone_on_reimport(api_client):
    """When re-importing with workplan_id, existing milestones should be reused."""
    from tests.factories import ProjectFactory, WorkplanFactory
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)

    # First import: create milestone
    payload = {
        "project_id": project.id,
        "workplan_id": workplan.id,
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Core Features",
                "description": "Initial description",
                "tasks": [{"ref": "task-1", "title": "Task One"}],
            }
        ],
        "links": [],
    }
    response1 = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response1.status_code == 201
    ref_map1 = response1.json()["ref_map"]
    milestone_id = ref_map1["phase-1"]

    # Verify milestone was created
    milestone = Milestone.objects.get(id=milestone_id)
    assert milestone.name == "Core Features"
    assert milestone.description == "Initial description"

    # Second import: same milestone name should reuse existing
    payload["milestones"][0]["description"] = "Updated description"
    payload["milestones"][0]["tasks"] = [{"ref": "task-2", "title": "Task Two"}]

    response2 = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response2.status_code == 201
    ref_map2 = response2.json()["ref_map"]

    # Same milestone ID should be returned
    assert ref_map2["phase-1"] == milestone_id

    # Milestone should have updated description
    milestone.refresh_from_db()
    assert milestone.name == "Core Features"
    assert milestone.description == "Updated description"

    # Both tasks should exist under the same milestone
    task1 = Task.objects.get(id=ref_map1["task-1"])
    task2 = Task.objects.get(id=ref_map2["task-2"])
    assert task1.milestone_id == milestone_id
    assert task2.milestone_id == milestone_id


@pytest.mark.django_db
def test_bulk_import_creates_new_milestone_when_name_differs(api_client):
    """When re-importing with different milestone name, new milestone should be created."""
    from tests.factories import ProjectFactory, WorkplanFactory
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)

    # First import
    payload1 = {
        "project_id": project.id,
        "workplan_id": workplan.id,
        "milestones": [
            {"ref": "phase-1", "name": "Phase One", "tasks": [{"ref": "task-1", "title": "Task One"}]}
        ],
        "links": [],
    }
    response1 = api_client.post(BULK_IMPORT_URL, data=payload1, format="json")
    assert response1.status_code == 201
    milestone1_id = response1.json()["ref_map"]["phase-1"]

    # Second import with different milestone name
    payload2 = {
        "project_id": project.id,
        "workplan_id": workplan.id,
        "milestones": [
            {"ref": "phase-2", "name": "Phase Two", "tasks": [{"ref": "task-2", "title": "Task Two"}]}
        ],
        "links": [],
    }
    response2 = api_client.post(BULK_IMPORT_URL, data=payload2, format="json")
    assert response2.status_code == 201
    milestone2_id = response2.json()["ref_map"]["phase-2"]

    # Should be different milestone IDs
    assert milestone1_id != milestone2_id

    # Both milestones should exist
    assert Milestone.objects.filter(id=milestone1_id, name="Phase One").exists()
    assert Milestone.objects.filter(id=milestone2_id, name="Phase Two").exists()


@pytest.mark.django_db
def test_bulk_import_new_workplan_always_creates_new_milestones(api_client):
    """When creating new workplan, milestones are always created even if names match existing."""
    from tests.factories import ProjectFactory
    project = ProjectFactory()

    # First workplan
    payload1 = {
        "project_id": project.id,
        "workplan": {"name": "Workplan One"},
        "milestones": [
            {"ref": "phase-1", "name": "Shared Name", "tasks": [{"ref": "task-1", "title": "Task One"}]}
        ],
        "links": [],
    }
    response1 = api_client.post(BULK_IMPORT_URL, data=payload1, format="json")
    assert response1.status_code == 201
    milestone1_id = response1.json()["ref_map"]["phase-1"]
    workplan1_id = response1.json()["ref_map"]["workplan"]

    # Second workplan with same milestone name
    payload2 = {
        "project_id": project.id,
        "workplan": {"name": "Workplan Two"},
        "milestones": [
            {"ref": "phase-2", "name": "Shared Name", "tasks": [{"ref": "task-2", "title": "Task Two"}]}
        ],
        "links": [],
    }
    response2 = api_client.post(BULK_IMPORT_URL, data=payload2, format="json")
    assert response2.status_code == 201
    milestone2_id = response2.json()["ref_map"]["phase-2"]
    workplan2_id = response2.json()["ref_map"]["workplan"]

    # Different workplans and milestones should be created
    assert workplan1_id != workplan2_id
    assert milestone1_id != milestone2_id

    # Both milestones should exist in different workplans
    milestone1 = Milestone.objects.get(id=milestone1_id)
    milestone2 = Milestone.objects.get(id=milestone2_id)
    assert milestone1.workplan_id == workplan1_id
    assert milestone2.workplan_id == workplan2_id
    assert milestone1.name == "Shared Name"
    assert milestone2.name == "Shared Name"


@pytest.mark.django_db
def test_bulk_import_preserves_existing_tasks_on_reimport(api_client):
    """Re-importing should add new tasks alongside existing ones, not replace them."""
    from tests.factories import ProjectFactory, WorkplanFactory
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)

    # First import with one task
    payload1 = {
        "project_id": project.id,
        "workplan_id": workplan.id,
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Development",
                "tasks": [{"ref": "task-1", "title": "Initial Task"}]
            }
        ],
        "links": [],
    }
    response1 = api_client.post(BULK_IMPORT_URL, data=payload1, format="json")
    assert response1.status_code == 201
    milestone_id = response1.json()["ref_map"]["phase-1"]
    task1_id = response1.json()["ref_map"]["task-1"]

    # Second import with different task
    payload2 = {
        "project_id": project.id,
        "workplan_id": workplan.id,
        "milestones": [
            {
                "ref": "phase-1",
                "name": "Development",
                "tasks": [{"ref": "task-2", "title": "Additional Task"}]
            }
        ],
        "links": [],
    }
    response2 = api_client.post(BULK_IMPORT_URL, data=payload2, format="json")
    assert response2.status_code == 201
    task2_id = response2.json()["ref_map"]["task-2"]

    # Both tasks should exist under the same milestone
    task1 = Task.objects.get(id=task1_id)
    task2 = Task.objects.get(id=task2_id)
    assert task1.milestone_id == milestone_id
    assert task2.milestone_id == milestone_id
    assert task1.title == "Initial Task"
    assert task2.title == "Additional Task"

    # Milestone should have 2 tasks total
    assert Task.objects.filter(milestone_id=milestone_id).count() == 2


@pytest.mark.django_db
def test_bulk_import_updates_milestone_description_on_reimport(api_client):
    """Re-importing should update milestone description if provided."""
    from tests.factories import ProjectFactory, WorkplanFactory
    project = ProjectFactory()
    workplan = WorkplanFactory(project=project)

    # First import with description
    payload = {
        "project_id": project.id,
        "workplan_id": workplan.id,
        "milestones": [
            {"ref": "phase-1", "name": "Feature Set", "description": "Original description"}
        ],
        "links": [],
    }
    response1 = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response1.status_code == 201
    milestone_id = response1.json()["ref_map"]["phase-1"]

    # Verify original description
    milestone = Milestone.objects.get(id=milestone_id)
    assert milestone.description == "Original description"

    # Re-import with updated description
    payload["milestones"][0]["description"] = "Updated description"
    response2 = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response2.status_code == 201

    # Description should be updated
    milestone.refresh_from_db()
    assert milestone.description == "Updated description"

    # Re-import without description (empty string)
    payload["milestones"][0]["description"] = ""
    response3 = api_client.post(BULK_IMPORT_URL, data=payload, format="json")
    assert response3.status_code == 201

    # Description should remain unchanged when empty string provided
    milestone.refresh_from_db()
    assert milestone.description == "Updated description"
