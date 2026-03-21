import pytest
from rest_framework import status

from tests.factories import ProjectFactory
from projects.models import Project


@pytest.fixture
def project(db):
    return ProjectFactory(name="Test Project", description="A test project")


@pytest.fixture
def archived_project(db):
    return ProjectFactory(name="Archived Project", status="archived")


@pytest.mark.django_db
class TestProjectList:
    def test_list_returns_200(self, api_client):
        response = api_client.get("/v1/projects/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_empty_when_no_projects(self, api_client):
        response = api_client.get("/v1/projects/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == []

    def test_list_returns_projects(self, api_client, project):
        response = api_client.get("/v1/projects/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == project.id
        assert response.data["results"][0]["name"] == project.name

    def test_list_uses_cursor_pagination(self, api_client, project):
        response = api_client.get("/v1/projects/")
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data


@pytest.mark.django_db
class TestProjectCreate:
    def test_create_returns_201(self, api_client):
        payload = {"name": "New Project"}
        response = api_client.post("/v1/projects/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_default_status(self, api_client):
        payload = {"name": "New Project"}
        response = api_client.post("/v1/projects/", payload, format="json")
        assert response.data["status"] == "active"

    def test_create_sets_default_branch(self, api_client):
        payload = {"name": "New Project"}
        response = api_client.post("/v1/projects/", payload, format="json")
        assert response.data["default_branch"] == "main"

    def test_create_returns_id(self, api_client):
        payload = {"name": "New Project"}
        response = api_client.post("/v1/projects/", payload, format="json")
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_with_all_fields(self, api_client):
        payload = {
            "name": "Full Project",
            "description": "A full project",
            "status": "active",
            "repo_url": "https://github.com/example/repo.git",
            "default_branch": "develop",
            "tags": ["backend", "api"],
            "owner": "alice",
            "created_by": "bob",
        }
        response = api_client.post("/v1/projects/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Full Project"
        assert response.data["description"] == "A full project"
        assert response.data["repo_url"] == "https://github.com/example/repo.git"
        assert response.data["default_branch"] == "develop"
        assert response.data["tags"] == ["backend", "api"]
        assert response.data["owner"] == "alice"
        assert response.data["created_by"] == "bob"

    def test_create_without_name_returns_400(self, api_client):
        response = api_client.post("/v1/projects/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_persists_to_db(self, api_client):
        payload = {"name": "Persistent Project"}
        response = api_client.post("/v1/projects/", payload, format="json")
        assert Project.objects.filter(id=response.data["id"]).exists()

    def test_create_id_is_read_only(self, api_client):
        payload = {"name": "Test", "id": "custom-id-12345678901"}
        response = api_client.post("/v1/projects/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["id"] != "custom-id-12345678901"


@pytest.mark.django_db
class TestProjectRetrieve:
    def test_retrieve_returns_200(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_returns_correct_data(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/")
        assert response.data["id"] == project.id
        assert response.data["name"] == project.name
        assert response.data["description"] == project.description

    def test_retrieve_returns_all_fields(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/")
        expected_fields = [
            "id", "name", "description", "status", "repo_url", "default_branch",
            "tags", "owner", "created_by", "created_at", "updated_at",
        ]
        for field in expected_fields:
            assert field in response.data

    def test_retrieve_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/projects/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProjectPartialUpdate:
    def test_patch_returns_200(self, api_client, project):
        response = api_client.patch(
            f"/v1/projects/{project.id}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patch_updates_field(self, api_client, project):
        response = api_client.patch(
            f"/v1/projects/{project.id}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert response.data["name"] == "Updated Name"

    def test_patch_persists_to_db(self, api_client, project):
        api_client.patch(
            f"/v1/projects/{project.id}/",
            {"description": "New description"},
            format="json",
        )
        project.refresh_from_db()
        assert project.description == "New description"

    def test_patch_does_not_affect_other_fields(self, api_client, project):
        original_name = project.name
        api_client.patch(
            f"/v1/projects/{project.id}/",
            {"description": "New description"},
            format="json",
        )
        project.refresh_from_db()
        assert project.name == original_name

    def test_put_not_allowed(self, api_client, project):
        response = api_client.put(
            f"/v1/projects/{project.id}/",
            {"name": "Updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_id_is_read_only(self, api_client, project):
        original_id = project.id
        api_client.patch(
            f"/v1/projects/{project.id}/",
            {"id": "newid1234567890123456"},
            format="json",
        )
        project.refresh_from_db()
        assert project.id == original_id

    def test_patch_timestamps_are_read_only(self, api_client, project):
        original_created_at = project.created_at
        api_client.patch(
            f"/v1/projects/{project.id}/",
            {"created_at": "2020-01-01T00:00:00Z"},
            format="json",
        )
        project.refresh_from_db()
        assert project.created_at == original_created_at


@pytest.mark.django_db
class TestProjectDelete:
    def test_delete_returns_204(self, api_client, project):
        response = api_client.delete(f"/v1/projects/{project.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_removes_from_db(self, api_client, project):
        api_client.delete(f"/v1/projects/{project.id}/")
        assert not Project.objects.filter(id=project.id).exists()

    def test_delete_nonexistent_returns_404(self, api_client):
        response = api_client.delete("/v1/projects/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProjectArchive:
    def test_archive_returns_200(self, api_client, project):
        response = api_client.post(f"/v1/projects/{project.id}/archive/")
        assert response.status_code == status.HTTP_200_OK

    def test_archive_sets_status(self, api_client, project):
        response = api_client.post(f"/v1/projects/{project.id}/archive/")
        assert response.data["status"] == "archived"

    def test_archive_persists_to_db(self, api_client, project):
        api_client.post(f"/v1/projects/{project.id}/archive/")
        project.refresh_from_db()
        assert project.status == "archived"

    def test_archive_already_archived_returns_400(self, api_client, archived_project):
        response = api_client.post(f"/v1/projects/{archived_project.id}/archive/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_archive_nonexistent_returns_404(self, api_client):
        response = api_client.post("/v1/projects/nonexistentid12345678/archive/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProjectStats:
    def test_stats_returns_200(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/stats/")
        assert response.status_code == status.HTTP_200_OK

    def test_stats_returns_project_id(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/stats/")
        assert response.data["project_id"] == project.id

    def test_stats_has_expected_keys(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/stats/")
        expected_keys = [
            "project_id", "total_tasks", "backlog_tasks", "workplan_tasks",
            "by_status", "completed_percentage", "workplans",
        ]
        for key in expected_keys:
            assert key in response.data

    def test_stats_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/projects/nonexistentid12345678/stats/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_stats_empty_project_returns_zeros(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/stats/")
        assert response.data["total_tasks"] == 0
        assert response.data["backlog_tasks"] == 0
        assert response.data["workplan_tasks"] == 0
        assert response.data["completed_percentage"] == 0.0
        assert response.data["by_status"] == {}

    def test_stats_workplan_counts(self, api_client, project):
        # Create workplans with different statuses linked to the project
        from tests.factories import WorkplanFactory
        WorkplanFactory(project=project, status="active")
        WorkplanFactory(project=project, status="active")
        WorkplanFactory(project=project, status="completed")
        WorkplanFactory(project=project, status="archived")

        response = api_client.get(f"/v1/projects/{project.id}/stats/")
        assert "workplans" in response.data
        workplan_counts = response.data["workplans"]
        assert workplan_counts.get("active", 0) == 2
        assert workplan_counts.get("completed", 0) == 1
        assert workplan_counts.get("archived", 0) == 1


@pytest.mark.django_db
class TestProjectWorkplansList:
    def test_workplans_list_returns_200(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/workplans/")
        assert response.status_code == status.HTTP_200_OK

    def test_workplans_list_nonexistent_project_returns_404(self, api_client):
        response = api_client.get("/v1/projects/nonexistentid12345678/workplans/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_workplans_list_has_pagination(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/workplans/")
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data

    def test_workplans_list_shows_linked_workplans(self, api_client, project):
        # Create workplans linked to the project
        from tests.factories import WorkplanFactory
        workplan1 = WorkplanFactory(project=project, name="Workplan 1")
        workplan2 = WorkplanFactory(project=project, name="Workplan 2")
        # Create a workplan for another project to ensure filtering works
        other_project = ProjectFactory(name="Other Project")
        WorkplanFactory(project=other_project, name="Other Workplan")

        response = api_client.get(f"/v1/projects/{project.id}/workplans/")
        assert len(response.data["results"]) == 2
        workplan_ids = [w["id"] for w in response.data["results"]]
        assert workplan1.id in workplan_ids
        assert workplan2.id in workplan_ids


@pytest.mark.django_db
class TestProjectBacklogList:
    def test_backlog_list_returns_200(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/backlog/")
        assert response.status_code == status.HTTP_200_OK

    def test_backlog_list_nonexistent_project_returns_404(self, api_client):
        response = api_client.get("/v1/projects/nonexistentid12345678/backlog/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_backlog_list_has_pagination(self, api_client, project):
        response = api_client.get(f"/v1/projects/{project.id}/backlog/")
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data

    def test_backlog_list_empty_for_now(self, api_client, project):
        # Since Task.project FK doesn't exist yet, this should be empty
        response = api_client.get(f"/v1/projects/{project.id}/backlog/")
        assert response.data["results"] == []