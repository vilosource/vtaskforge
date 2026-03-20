import pytest
from rest_framework import status

from tests.factories import PhaseFactory, WorkplanFactory
from workplans.models import Phase


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan", description="A test workplan")


@pytest.fixture
def other_workplan(db):
    return WorkplanFactory(name="Other Workplan")


@pytest.fixture
def pending_phase(db, workplan):
    return PhaseFactory(name="Pending Phase", workplan=workplan)


@pytest.fixture
def active_phase(db, workplan):
    return PhaseFactory(name="Active Phase", workplan=workplan, status="active")


@pytest.fixture
def completed_phase(db, workplan):
    return PhaseFactory(name="Completed Phase", workplan=workplan, status="completed")


@pytest.mark.django_db
class TestNestedPhaseCreate:
    def test_create_returns_201(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            {"name": "Phase 1"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_default_status_pending(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            {"name": "Phase 1"},
            format="json",
        )
        assert response.data["status"] == "pending"

    def test_create_returns_id(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            {"name": "Phase 1"},
            format="json",
        )
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_sets_workplan_reference(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            {"name": "Phase 1"},
            format="json",
        )
        assert response.data["workplan"] == workplan.id

    def test_create_without_name_returns_400(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_nonexistent_workplan_returns_404(self, api_client):
        response = api_client.post(
            "/v1/workplans/nonexistentid12345678/phases/",
            {"name": "Phase 1"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_persists_to_db(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            {"name": "Persistent Phase"},
            format="json",
        )
        assert Phase.objects.filter(id=response.data["id"]).exists()

    def test_create_with_all_fields(self, api_client, workplan):
        payload = {
            "name": "Full Phase",
            "description": "A full phase",
            "order": 3,
            "created_by": "alice",
        }
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Full Phase"
        assert response.data["description"] == "A full phase"
        assert response.data["order"] == 3
        assert response.data["created_by"] == "alice"

    def test_create_with_null_review_flags(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/phases/",
            {"name": "Phase", "default_needs_review_before_start": None},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["default_needs_review_before_start"] is None


@pytest.mark.django_db
class TestNestedPhaseList:
    def test_list_returns_200(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/phases/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_empty_when_no_phases(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/phases/")
        assert response.data == []

    def test_list_returns_phases_for_workplan(self, api_client, workplan, pending_phase):
        response = api_client.get(f"/v1/workplans/{workplan.id}/phases/")
        assert len(response.data) == 1
        assert response.data[0]["id"] == pending_phase.id

    def test_list_does_not_include_other_workplan_phases(
        self, api_client, workplan, other_workplan
    ):
        PhaseFactory(name="Phase A", workplan=workplan)
        PhaseFactory(name="Phase B", workplan=other_workplan)
        response = api_client.get(f"/v1/workplans/{workplan.id}/phases/")
        assert len(response.data) == 1

    def test_list_nonexistent_workplan_returns_404(self, api_client):
        response = api_client.get("/v1/workplans/nonexistentid12345678/phases/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPhaseRetrieve:
    def test_retrieve_returns_200(self, api_client, pending_phase):
        response = api_client.get(f"/v1/phases/{pending_phase.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_returns_correct_data(self, api_client, pending_phase):
        response = api_client.get(f"/v1/phases/{pending_phase.id}/")
        assert response.data["id"] == pending_phase.id
        assert response.data["name"] == pending_phase.name

    def test_retrieve_returns_all_fields(self, api_client, pending_phase):
        response = api_client.get(f"/v1/phases/{pending_phase.id}/")
        expected_fields = [
            "id", "name", "description", "workplan", "status", "order",
            "default_needs_review_before_start", "default_needs_review_on_completion",
            "created_by", "created_at", "updated_at",
        ]
        for field in expected_fields:
            assert field in response.data

    def test_retrieve_includes_workplan_reference(self, api_client, pending_phase, workplan):
        response = api_client.get(f"/v1/phases/{pending_phase.id}/")
        assert response.data["workplan"] == workplan.id

    def test_retrieve_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/phases/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPhasePartialUpdate:
    def test_patch_returns_200(self, api_client, pending_phase):
        response = api_client.patch(
            f"/v1/phases/{pending_phase.id}/",
            {"description": "updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patch_updates_field(self, api_client, pending_phase):
        response = api_client.patch(
            f"/v1/phases/{pending_phase.id}/",
            {"description": "updated description"},
            format="json",
        )
        assert response.data["description"] == "updated description"

    def test_patch_persists_to_db(self, api_client, pending_phase):
        api_client.patch(
            f"/v1/phases/{pending_phase.id}/",
            {"name": "Updated Name"},
            format="json",
        )
        pending_phase.refresh_from_db()
        assert pending_phase.name == "Updated Name"

    def test_put_not_allowed(self, api_client, pending_phase):
        response = api_client.put(
            f"/v1/phases/{pending_phase.id}/",
            {"name": "Updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_id_is_read_only(self, api_client, pending_phase):
        original_id = pending_phase.id
        api_client.patch(
            f"/v1/phases/{pending_phase.id}/",
            {"id": "newid1234567890123456"},
            format="json",
        )
        pending_phase.refresh_from_db()
        assert pending_phase.id == original_id


@pytest.mark.django_db
class TestPhaseActivate:
    def test_activate_pending_phase_returns_200(self, api_client, pending_phase):
        response = api_client.post(f"/v1/phases/{pending_phase.id}/activate/")
        assert response.status_code == status.HTTP_200_OK

    def test_activate_sets_status_active(self, api_client, pending_phase):
        response = api_client.post(f"/v1/phases/{pending_phase.id}/activate/")
        assert response.data["status"] == "active"

    def test_activate_persists_to_db(self, api_client, pending_phase):
        api_client.post(f"/v1/phases/{pending_phase.id}/activate/")
        pending_phase.refresh_from_db()
        assert pending_phase.status == "active"

    def test_activate_active_phase_returns_400(self, api_client, active_phase):
        response = api_client.post(f"/v1/phases/{active_phase.id}/activate/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_activate_completed_phase_returns_400(self, api_client, completed_phase):
        response = api_client.post(f"/v1/phases/{completed_phase.id}/activate/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPhaseComplete:
    def test_complete_active_phase_returns_200(self, api_client, active_phase):
        response = api_client.post(f"/v1/phases/{active_phase.id}/complete/")
        assert response.status_code == status.HTTP_200_OK

    def test_complete_sets_status_completed(self, api_client, active_phase):
        response = api_client.post(f"/v1/phases/{active_phase.id}/complete/")
        assert response.data["status"] == "completed"

    def test_complete_persists_to_db(self, api_client, active_phase):
        api_client.post(f"/v1/phases/{active_phase.id}/complete/")
        active_phase.refresh_from_db()
        assert active_phase.status == "completed"

    def test_complete_pending_phase_returns_400(self, api_client, pending_phase):
        response = api_client.post(f"/v1/phases/{pending_phase.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_already_completed_returns_400(self, api_client, completed_phase):
        response = api_client.post(f"/v1/phases/{completed_phase.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPhaseStats:
    def test_stats_returns_200(self, api_client, pending_phase):
        response = api_client.get(f"/v1/phases/{pending_phase.id}/stats/")
        assert response.status_code == status.HTTP_200_OK

    def test_stats_returns_phase_id(self, api_client, pending_phase):
        response = api_client.get(f"/v1/phases/{pending_phase.id}/stats/")
        assert response.data["phase_id"] == pending_phase.id

    def test_stats_has_expected_keys(self, api_client, pending_phase):
        response = api_client.get(f"/v1/phases/{pending_phase.id}/stats/")
        assert "total_tasks" in response.data
        assert "completed_tasks" in response.data
        assert "pending_tasks" in response.data
        assert "in_progress_tasks" in response.data

    def test_stats_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/phases/nonexistentid12345678/stats/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
