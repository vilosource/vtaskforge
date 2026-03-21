"""
Tests for backlog tasks (project-only tasks without workplan/milestone).
"""
import pytest
from rest_framework import status

from tasks.models import Task
from tests.factories import BacklogTaskFactory, MilestoneFactory, ProjectFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project(db):
    return ProjectFactory(name="Test Project")


@pytest.fixture
def backlog_task(db, project):
    return BacklogTaskFactory(project=project)


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBacklogTaskValidation:
    def test_create_task_with_only_project(self, project):
        """Can create a task with only project (no workplan, no milestone)."""
        task = Task.objects.create(
            title="Backlog Task",
            project=project,
            workplan=None,
            milestone=None,
        )
        assert task.project == project
        assert task.workplan is None
        assert task.milestone is None
        assert task.labels == []

    def test_create_task_with_project_and_workplan_no_milestone(self, project):
        """Can create a task with project + workplan but no milestone."""
        workplan = WorkplanFactory(project=project)
        task = Task.objects.create(
            title="Workplan Task",
            project=project,
            workplan=workplan,
            milestone=None,
        )
        assert task.project == project
        assert task.workplan == workplan
        assert task.milestone is None

    def test_labels_defaults_to_empty_list(self, project):
        """Labels field defaults to empty list."""
        task = Task.objects.create(
            title="Task",
            project=project,
        )
        assert task.labels == []

    def test_can_set_labels(self, project):
        """Can set labels on task."""
        task = Task.objects.create(
            title="Task",
            project=project,
            labels=["bugfix", "urgent"],
        )
        assert task.labels == ["bugfix", "urgent"]


# ---------------------------------------------------------------------------
# Serializer validation tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTaskSerializerValidation:
    def test_project_required_on_create(self, api_client):
        """project field is required when creating a task."""
        payload = {"title": "Task"}
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "project" in str(response.data)

    def test_milestone_without_workplan_fails(self, api_client, project):
        """Cannot create task with milestone but no workplan."""
        workplan = WorkplanFactory(project=project)
        milestone = MilestoneFactory(workplan=workplan)
        payload = {
            "title": "Invalid Task",
            "project": project.id,
            "milestone": milestone.id,
            # workplan intentionally missing
        }
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "workplan must also be set" in str(response.data)

    def test_milestone_workplan_mismatch_fails(self, api_client, project):
        """Cannot create task where milestone.workplan != workplan."""
        workplan1 = WorkplanFactory(project=project)
        workplan2 = WorkplanFactory(project=project)
        milestone = MilestoneFactory(workplan=workplan1)
        payload = {
            "title": "Invalid Task",
            "project": project.id,
            "milestone": milestone.id,
            "workplan": workplan2.id,  # Different workplan
        }
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "milestone.workplan must equal workplan" in str(response.data)

    def test_workplan_project_mismatch_fails(self, api_client):
        """Cannot create task where workplan.project != project."""
        project1 = ProjectFactory()
        project2 = ProjectFactory()
        workplan = WorkplanFactory(project=project1)
        payload = {
            "title": "Invalid Task",
            "project": project2.id,  # Different project
            "workplan": workplan.id,
        }
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "workplan.project must equal project" in str(response.data)

    def test_valid_backlog_task_creation(self, api_client, project):
        """Can create valid backlog task (project only)."""
        payload = {
            "title": "Backlog Task",
            "project": project.id,
            "labels": ["bugfix", "urgent"],
        }
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project"] == project.id
        assert response.data["workplan"] is None
        assert response.data["milestone"] is None
        assert response.data["labels"] == ["bugfix", "urgent"]

    def test_valid_workplan_task_creation(self, api_client, project):
        """Can create valid workplan task (project + workplan, no milestone)."""
        workplan = WorkplanFactory(project=project)
        payload = {
            "title": "Workplan Task",
            "project": project.id,
            "workplan": workplan.id,
        }
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project"] == project.id
        assert response.data["workplan"] == workplan.id
        assert response.data["milestone"] is None

    def test_valid_milestone_task_creation(self, api_client, project):
        """Can create valid milestone task (project + workplan + milestone)."""
        workplan = WorkplanFactory(project=project)
        milestone = MilestoneFactory(workplan=workplan)
        payload = {
            "title": "Milestone Task",
            "project": project.id,
            "workplan": workplan.id,
            "milestone": milestone.id,
        }
        response = api_client.post("/v1/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project"] == project.id
        assert response.data["workplan"] == workplan.id
        assert response.data["milestone"] == milestone.id


# ---------------------------------------------------------------------------
# Project filtering tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProjectFiltering:
    def test_filter_tasks_by_project(self, api_client):
        """GET /v1/tasks/?project=:id filters by project."""
        project1 = ProjectFactory()
        project2 = ProjectFactory()
        task1 = BacklogTaskFactory(project=project1)
        task2 = BacklogTaskFactory(project=project2)

        response = api_client.get(f"/v1/tasks/?project={project1.id}")
        assert response.status_code == status.HTTP_200_OK
        result_ids = [t["id"] for t in response.data["results"]]
        assert task1.id in result_ids
        assert task2.id not in result_ids

    def test_claimable_endpoint_with_project_filter(self, api_client, project):
        """GET /v1/tasks/claimable?project=:id scopes discovery."""
        # Create todo tasks in different projects
        project2 = ProjectFactory()
        task1 = BacklogTaskFactory(project=project, status="todo")
        task2 = BacklogTaskFactory(project=project2, status="todo")

        response = api_client.get(f"/v1/tasks/claimable/?project={project.id}")
        assert response.status_code == status.HTTP_200_OK
        result_ids = [t["id"] for t in response.data["results"]]
        assert task1.id in result_ids
        assert task2.id not in result_ids


# ---------------------------------------------------------------------------
# Labels filtering tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLabelsFiltering:
    def test_filter_tasks_by_single_label(self, api_client, project):
        """GET /v1/tasks/?labels=bugfix filters by label."""
        task1 = BacklogTaskFactory(project=project, labels=["bugfix"])
        task2 = BacklogTaskFactory(project=project, labels=["feature"])
        task3 = BacklogTaskFactory(project=project, labels=["bugfix", "urgent"])

        response = api_client.get("/v1/tasks/?labels=bugfix")
        assert response.status_code == status.HTTP_200_OK
        result_ids = [t["id"] for t in response.data["results"]]
        assert task1.id in result_ids
        assert task2.id not in result_ids
        assert task3.id in result_ids

    def test_filter_tasks_by_multiple_labels(self, api_client, project):
        """GET /v1/tasks/?labels=bugfix,urgent filters by any of the labels."""
        task1 = BacklogTaskFactory(project=project, labels=["bugfix"])
        task2 = BacklogTaskFactory(project=project, labels=["urgent"])
        task3 = BacklogTaskFactory(project=project, labels=["feature"])
        task4 = BacklogTaskFactory(project=project, labels=["bugfix", "urgent"])

        response = api_client.get("/v1/tasks/?labels=bugfix,urgent")
        assert response.status_code == status.HTTP_200_OK
        result_ids = [t["id"] for t in response.data["results"]]
        # Should include tasks with bugfix OR urgent
        assert task1.id in result_ids  # has bugfix
        assert task2.id in result_ids  # has urgent
        assert task3.id not in result_ids  # has neither
        assert task4.id in result_ids  # has both


# ---------------------------------------------------------------------------
# ProjectTasksView endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProjectTasksEndpoint:
    def test_get_project_tasks_returns_backlog_only(self, api_client, project):
        """GET /v1/projects/:id/tasks/ returns only backlog tasks."""
        workplan = WorkplanFactory(project=project)
        milestone = MilestoneFactory(workplan=workplan)

        backlog_task = BacklogTaskFactory(project=project)
        workplan_task = TaskFactory(project=project, workplan=workplan, milestone=milestone)

        response = api_client.get(f"/v1/projects/{project.id}/tasks/")
        assert response.status_code == status.HTTP_200_OK
        result_ids = [t["id"] for t in response.data["results"]]
        assert backlog_task.id in result_ids
        assert workplan_task.id not in result_ids

    def test_post_creates_backlog_task(self, api_client, project):
        """POST /v1/projects/:id/tasks/ creates backlog task."""
        payload = {
            "title": "Backlog Task",
            "labels": ["bugfix"],
        }
        response = api_client.post(f"/v1/projects/{project.id}/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project"] == project.id
        assert response.data["workplan"] is None
        assert response.data["milestone"] is None
        assert response.data["labels"] == ["bugfix"]

    def test_post_ignores_workplan_milestone_in_payload(self, api_client, project):
        """POST /v1/projects/:id/tasks/ ignores workplan/milestone in payload."""
        workplan = WorkplanFactory(project=project)
        milestone = MilestoneFactory(workplan=workplan)

        payload = {
            "title": "Backlog Task",
            "workplan": workplan.id,  # Should be ignored
            "milestone": milestone.id,  # Should be ignored
        }
        response = api_client.post(f"/v1/projects/{project.id}/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project"] == project.id
        assert response.data["workplan"] is None
        assert response.data["milestone"] is None

    def test_get_project_tasks_filters_by_status(self, api_client, project):
        """GET /v1/projects/:id/tasks/?status=todo filters backlog tasks."""
        task1 = BacklogTaskFactory(project=project, status="draft")
        task2 = BacklogTaskFactory(project=project, status="todo")

        response = api_client.get(f"/v1/projects/{project.id}/tasks/?status=todo")
        assert response.status_code == status.HTTP_200_OK
        result_ids = [t["id"] for t in response.data["results"]]
        assert task1.id not in result_ids
        assert task2.id in result_ids

    def test_get_project_tasks_filters_by_labels(self, api_client, project):
        """GET /v1/projects/:id/tasks/?labels=bugfix filters backlog tasks."""
        task1 = BacklogTaskFactory(project=project, labels=["bugfix"])
        task2 = BacklogTaskFactory(project=project, labels=["feature"])

        response = api_client.get(f"/v1/projects/{project.id}/tasks/?labels=bugfix")
        assert response.status_code == status.HTTP_200_OK
        result_ids = [t["id"] for t in response.data["results"]]
        assert task1.id in result_ids
        assert task2.id not in result_ids

    def test_get_project_tasks_404_for_unknown_project(self, api_client):
        """GET /v1/projects/unknown/tasks/ returns 404."""
        response = api_client.get("/v1/projects/nonexistentid12345678/tasks/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_post_project_tasks_404_for_unknown_project(self, api_client):
        """POST /v1/projects/unknown/tasks/ returns 404."""
        payload = {"title": "Task"}
        response = api_client.post("/v1/projects/nonexistentid12345678/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# MilestoneTasksView project auto-setting tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMilestoneTasksProjectAutoSetting:
    def test_milestone_tasks_auto_sets_project(self, api_client, project):
        """POST /v1/milestones/:id/tasks/ auto-sets project from milestone.workplan.project."""
        workplan = WorkplanFactory(project=project)
        milestone = MilestoneFactory(workplan=workplan)

        payload = {"title": "Milestone Task"}
        response = api_client.post(f"/v1/milestones/{milestone.id}/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["project"] == project.id
        assert response.data["workplan"] == workplan.id
        assert response.data["milestone"] == milestone.id