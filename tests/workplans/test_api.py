import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from workplans.models import Workplan


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def workplan(db):
    return Workplan.objects.create(name="Test Workplan", description="A test workplan")


@pytest.fixture
def archived_workplan(db):
    return Workplan.objects.create(name="Archived Workplan", status="archived")


@pytest.fixture
def completed_workplan(db):
    return Workplan.objects.create(name="Completed Workplan", status="completed")


@pytest.mark.django_db
class TestWorkplanList:
    def test_list_returns_200(self, api_client):
        response = api_client.get("/v1/workplans/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_empty_when_no_workplans(self, api_client):
        response = api_client.get("/v1/workplans/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_list_returns_workplans(self, api_client, workplan):
        response = api_client.get("/v1/workplans/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == workplan.id
        assert response.data[0]["name"] == workplan.name


@pytest.mark.django_db
class TestWorkplanCreate:
    def test_create_returns_201(self, api_client):
        payload = {"name": "New Workplan"}
        response = api_client.post("/v1/workplans/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_default_status(self, api_client):
        payload = {"name": "New Workplan"}
        response = api_client.post("/v1/workplans/", payload, format="json")
        assert response.data["status"] == "active"

    def test_create_returns_id(self, api_client):
        payload = {"name": "New Workplan"}
        response = api_client.post("/v1/workplans/", payload, format="json")
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_with_all_fields(self, api_client):
        payload = {
            "name": "Full Workplan",
            "description": "A full workplan",
            "status": "active",
            "owner": "alice",
            "tags": ["backend", "api"],
            "created_by": "bob",
        }
        response = api_client.post("/v1/workplans/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Full Workplan"
        assert response.data["description"] == "A full workplan"
        assert response.data["owner"] == "alice"
        assert response.data["tags"] == ["backend", "api"]
        assert response.data["created_by"] == "bob"

    def test_create_without_name_returns_400(self, api_client):
        response = api_client.post("/v1/workplans/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_persists_to_db(self, api_client):
        payload = {"name": "Persistent Workplan"}
        response = api_client.post("/v1/workplans/", payload, format="json")
        assert Workplan.objects.filter(id=response.data["id"]).exists()

    def test_create_id_is_read_only(self, api_client):
        payload = {"name": "Test", "id": "custom-id-12345678901"}
        response = api_client.post("/v1/workplans/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["id"] != "custom-id-12345678901"


@pytest.mark.django_db
class TestWorkplanRetrieve:
    def test_retrieve_returns_200(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_returns_correct_data(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/")
        assert response.data["id"] == workplan.id
        assert response.data["name"] == workplan.name
        assert response.data["description"] == workplan.description

    def test_retrieve_returns_all_fields(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/")
        expected_fields = [
            "id", "name", "description", "status", "owner", "tags",
            "target_date", "default_needs_review_before_start",
            "default_needs_review_on_completion", "created_by",
            "created_at", "updated_at",
        ]
        for field in expected_fields:
            assert field in response.data

    def test_retrieve_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/workplans/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestWorkplanPartialUpdate:
    def test_patch_returns_200(self, api_client, workplan):
        response = api_client.patch(
            f"/v1/workplans/{workplan.id}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patch_updates_field(self, api_client, workplan):
        response = api_client.patch(
            f"/v1/workplans/{workplan.id}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert response.data["name"] == "Updated Name"

    def test_patch_persists_to_db(self, api_client, workplan):
        api_client.patch(
            f"/v1/workplans/{workplan.id}/",
            {"description": "New description"},
            format="json",
        )
        workplan.refresh_from_db()
        assert workplan.description == "New description"

    def test_patch_does_not_affect_other_fields(self, api_client, workplan):
        original_name = workplan.name
        api_client.patch(
            f"/v1/workplans/{workplan.id}/",
            {"description": "New description"},
            format="json",
        )
        workplan.refresh_from_db()
        assert workplan.name == original_name

    def test_put_not_allowed(self, api_client, workplan):
        response = api_client.put(
            f"/v1/workplans/{workplan.id}/",
            {"name": "Updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_id_is_read_only(self, api_client, workplan):
        original_id = workplan.id
        api_client.patch(
            f"/v1/workplans/{workplan.id}/",
            {"id": "newid1234567890123456"},
            format="json",
        )
        workplan.refresh_from_db()
        assert workplan.id == original_id


@pytest.mark.django_db
class TestWorkplanArchive:
    def test_archive_returns_200(self, api_client, workplan):
        response = api_client.post(f"/v1/workplans/{workplan.id}/archive/")
        assert response.status_code == status.HTTP_200_OK

    def test_archive_sets_status(self, api_client, workplan):
        response = api_client.post(f"/v1/workplans/{workplan.id}/archive/")
        assert response.data["status"] == "archived"

    def test_archive_persists_to_db(self, api_client, workplan):
        api_client.post(f"/v1/workplans/{workplan.id}/archive/")
        workplan.refresh_from_db()
        assert workplan.status == "archived"

    def test_archive_already_archived_returns_400(self, api_client, archived_workplan):
        response = api_client.post(f"/v1/workplans/{archived_workplan.id}/archive/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_archive_completed_workplan_succeeds(self, api_client, completed_workplan):
        response = api_client.post(f"/v1/workplans/{completed_workplan.id}/archive/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "archived"


@pytest.mark.django_db
class TestWorkplanComplete:
    def test_complete_returns_200(self, api_client, workplan):
        response = api_client.post(f"/v1/workplans/{workplan.id}/complete/")
        assert response.status_code == status.HTTP_200_OK

    def test_complete_sets_status(self, api_client, workplan):
        response = api_client.post(f"/v1/workplans/{workplan.id}/complete/")
        assert response.data["status"] == "completed"

    def test_complete_persists_to_db(self, api_client, workplan):
        api_client.post(f"/v1/workplans/{workplan.id}/complete/")
        workplan.refresh_from_db()
        assert workplan.status == "completed"

    def test_complete_already_completed_returns_400(self, api_client, completed_workplan):
        response = api_client.post(f"/v1/workplans/{completed_workplan.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_archived_workplan_returns_400(self, api_client, archived_workplan):
        response = api_client.post(f"/v1/workplans/{archived_workplan.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestWorkplanStats:
    def test_stats_returns_200(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/stats/")
        assert response.status_code == status.HTTP_200_OK

    def test_stats_returns_workplan_id(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/stats/")
        assert response.data["workplan_id"] == workplan.id

    def test_stats_has_expected_keys(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/stats/")
        assert "total_tasks" in response.data
        assert "completed_tasks" in response.data
        assert "pending_tasks" in response.data
        assert "in_progress_tasks" in response.data

    def test_stats_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/workplans/nonexistentid12345678/stats/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
