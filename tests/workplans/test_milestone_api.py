import pytest
from rest_framework import status

from tests.factories import MilestoneFactory, TaskFactory, WorkplanFactory
from workplans.models import Milestone


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan", description="A test workplan")


@pytest.fixture
def other_workplan(db):
    return WorkplanFactory(name="Other Workplan")


@pytest.fixture
def pending_milestone(db, workplan):
    return MilestoneFactory(name="Pending Milestone", workplan=workplan, status="pending")


@pytest.fixture
def active_milestone(db, workplan):
    return MilestoneFactory(name="Active Milestone", workplan=workplan, status="active")


@pytest.fixture
def completed_milestone(db, workplan):
    return MilestoneFactory(name="Completed Milestone", workplan=workplan, status="completed")


@pytest.mark.django_db
class TestNestedMilestoneCreate:
    def test_create_returns_201(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            {"name": "Milestone 1"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_sets_default_status_pending(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            {"name": "Milestone 1"},
            format="json",
        )
        assert response.data["status"] == "pending"

    def test_create_returns_id(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            {"name": "Milestone 1"},
            format="json",
        )
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_sets_workplan_reference(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            {"name": "Milestone 1"},
            format="json",
        )
        assert response.data["workplan"] == workplan.id

    def test_create_without_name_returns_400(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_nonexistent_workplan_returns_404(self, api_client):
        response = api_client.post(
            "/v1/workplans/nonexistentid12345678/milestones/",
            {"name": "Milestone 1"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_persists_to_db(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            {"name": "Persistent Milestone"},
            format="json",
        )
        assert Milestone.objects.filter(id=response.data["id"]).exists()

    def test_create_with_all_fields(self, api_client, workplan):
        payload = {
            "name": "Full Milestone",
            "description": "A full milestone",
            "order": 3,
            "created_by": "alice",
        }
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Full Milestone"
        assert response.data["description"] == "A full milestone"
        assert response.data["order"] == 3
        assert response.data["created_by"] == "alice"

    def test_create_with_null_review_flags(self, api_client, workplan):
        response = api_client.post(
            f"/v1/workplans/{workplan.id}/milestones/",
            {"name": "Milestone", "default_needs_review_before_start": None},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["default_needs_review_before_start"] is None


@pytest.mark.django_db
class TestNestedMilestoneList:
    def test_list_returns_200(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/milestones/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_empty_when_no_milestones(self, api_client, workplan):
        response = api_client.get(f"/v1/workplans/{workplan.id}/milestones/")
        assert response.data["results"] == []

    def test_list_returns_milestones_for_workplan(self, api_client, workplan, pending_milestone):
        response = api_client.get(f"/v1/workplans/{workplan.id}/milestones/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == pending_milestone.id

    def test_list_does_not_include_other_workplan_milestones(
        self, api_client, workplan, other_workplan
    ):
        MilestoneFactory(name="Milestone A", workplan=workplan)
        MilestoneFactory(name="Milestone B", workplan=other_workplan)
        response = api_client.get(f"/v1/workplans/{workplan.id}/milestones/")
        assert len(response.data["results"]) == 1

    def test_list_nonexistent_workplan_returns_404(self, api_client):
        response = api_client.get("/v1/workplans/nonexistentid12345678/milestones/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestMilestoneRetrieve:
    def test_retrieve_returns_200(self, api_client, pending_milestone):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_returns_correct_data(self, api_client, pending_milestone):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/")
        assert response.data["id"] == pending_milestone.id
        assert response.data["name"] == pending_milestone.name

    def test_retrieve_returns_all_fields(self, api_client, pending_milestone):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/")
        expected_fields = [
            "id", "name", "description", "workplan", "status", "order",
            "default_needs_review_before_start", "default_needs_review_on_completion",
            "created_by", "created_at", "updated_at",
        ]
        for field in expected_fields:
            assert field in response.data

    def test_retrieve_includes_workplan_reference(self, api_client, pending_milestone, workplan):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/")
        assert response.data["workplan"] == workplan.id

    def test_retrieve_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/milestones/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestMilestonePartialUpdate:
    def test_patch_returns_200(self, api_client, pending_milestone):
        response = api_client.patch(
            f"/v1/milestones/{pending_milestone.id}/",
            {"description": "updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_patch_updates_field(self, api_client, pending_milestone):
        response = api_client.patch(
            f"/v1/milestones/{pending_milestone.id}/",
            {"description": "updated description"},
            format="json",
        )
        assert response.data["description"] == "updated description"

    def test_patch_persists_to_db(self, api_client, pending_milestone):
        api_client.patch(
            f"/v1/milestones/{pending_milestone.id}/",
            {"name": "Updated Name"},
            format="json",
        )
        pending_milestone.refresh_from_db()
        assert pending_milestone.name == "Updated Name"

    def test_put_not_allowed(self, api_client, pending_milestone):
        response = api_client.put(
            f"/v1/milestones/{pending_milestone.id}/",
            {"name": "Updated"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_id_is_read_only(self, api_client, pending_milestone):
        original_id = pending_milestone.id
        api_client.patch(
            f"/v1/milestones/{pending_milestone.id}/",
            {"id": "newid1234567890123456"},
            format="json",
        )
        pending_milestone.refresh_from_db()
        assert pending_milestone.id == original_id


@pytest.mark.django_db
class TestMilestoneActivate:
    def test_activate_pending_milestone_returns_200(self, api_client, pending_milestone):
        response = api_client.post(f"/v1/milestones/{pending_milestone.id}/activate/")
        assert response.status_code == status.HTTP_200_OK

    def test_activate_sets_status_active(self, api_client, pending_milestone):
        response = api_client.post(f"/v1/milestones/{pending_milestone.id}/activate/")
        assert response.data["status"] == "active"

    def test_activate_persists_to_db(self, api_client, pending_milestone):
        api_client.post(f"/v1/milestones/{pending_milestone.id}/activate/")
        pending_milestone.refresh_from_db()
        assert pending_milestone.status == "active"

    def test_activate_active_milestone_returns_400(self, api_client, active_milestone):
        response = api_client.post(f"/v1/milestones/{active_milestone.id}/activate/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_activate_completed_milestone_returns_400(self, api_client, completed_milestone):
        response = api_client.post(f"/v1/milestones/{completed_milestone.id}/activate/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_activate_skips_to_completed_when_all_tasks_terminal(self, api_client, workplan):
        """Activating a milestone where all tasks are done goes straight to completed."""
        ms = MilestoneFactory(name="All Done", workplan=workplan, status="pending")
        TaskFactory(title="T1", milestone=ms, workplan=workplan, status="done")
        TaskFactory(title="T2", milestone=ms, workplan=workplan, status="cancelled")
        response = api_client.post(f"/v1/milestones/{ms.id}/activate/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "completed"

    def test_activate_goes_to_active_when_tasks_remain(self, api_client, workplan):
        ms = MilestoneFactory(name="Has Work", workplan=workplan, status="pending")
        TaskFactory(title="T1", milestone=ms, workplan=workplan, status="done")
        TaskFactory(title="T2", milestone=ms, workplan=workplan, status="draft")
        response = api_client.post(f"/v1/milestones/{ms.id}/activate/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "active"

    def test_activate_empty_milestone_goes_to_active(self, api_client, workplan):
        """Empty milestone (no tasks) activates normally."""
        ms = MilestoneFactory(name="Empty", workplan=workplan, status="pending")
        response = api_client.post(f"/v1/milestones/{ms.id}/activate/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "active"


@pytest.mark.django_db
class TestMilestoneComplete:
    def test_complete_active_milestone_returns_200(self, api_client, active_milestone):
        response = api_client.post(f"/v1/milestones/{active_milestone.id}/complete/")
        assert response.status_code == status.HTTP_200_OK

    def test_complete_sets_status_completed(self, api_client, active_milestone):
        response = api_client.post(f"/v1/milestones/{active_milestone.id}/complete/")
        assert response.data["status"] == "completed"

    def test_complete_persists_to_db(self, api_client, active_milestone):
        api_client.post(f"/v1/milestones/{active_milestone.id}/complete/")
        active_milestone.refresh_from_db()
        assert active_milestone.status == "completed"

    def test_complete_pending_milestone_returns_400(self, api_client, pending_milestone):
        response = api_client.post(f"/v1/milestones/{pending_milestone.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_already_completed_returns_400(self, api_client, completed_milestone):
        response = api_client.post(f"/v1/milestones/{completed_milestone.id}/complete/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestMilestoneStats:
    def test_stats_returns_200(self, api_client, pending_milestone):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert response.status_code == status.HTTP_200_OK

    def test_stats_returns_milestone_id(self, api_client, pending_milestone):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert response.data["milestone_id"] == pending_milestone.id

    def test_stats_has_expected_keys(self, api_client, pending_milestone):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert "total_tasks" in response.data
        assert "completed_tasks" in response.data
        assert "pending_tasks" in response.data
        assert "in_progress_tasks" in response.data

    def test_stats_nonexistent_returns_404(self, api_client):
        response = api_client.get("/v1/milestones/nonexistentid12345678/stats/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_stats_empty_milestone_returns_zeros(self, api_client, pending_milestone):
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert response.data["total_tasks"] == 0
        assert response.data["completed_percentage"] == 0.0
        assert response.data["by_status"] == {}

    def test_stats_counts_tasks_by_status(self, api_client, workplan, pending_milestone):
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="todo")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="todo")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="doing")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="done")
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert response.data["total_tasks"] == 4
        assert response.data["by_status"]["todo"] == 2
        assert response.data["by_status"]["doing"] == 1
        assert response.data["by_status"]["done"] == 1

    def test_stats_completed_percentage(self, api_client, workplan, pending_milestone):
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="done")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="done")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="todo")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="todo")
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert response.data["completed_percentage"] == 50.0

    def test_stats_completed_percentage_is_float(self, api_client, workplan, pending_milestone):
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="done")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="todo")
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="todo")
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert isinstance(response.data["completed_percentage"], float)

    def test_stats_only_counts_own_milestone_tasks(self, api_client, workplan, pending_milestone):
        other_milestone = MilestoneFactory(workplan=workplan)
        TaskFactory(workplan=workplan, milestone=pending_milestone, status="done")
        TaskFactory(workplan=workplan, milestone=other_milestone, status="done")
        response = api_client.get(f"/v1/milestones/{pending_milestone.id}/stats/")
        assert response.data["total_tasks"] == 1
