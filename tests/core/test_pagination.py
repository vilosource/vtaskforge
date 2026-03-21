"""
Tests for VTFCursorPagination.
"""
import pytest
from rest_framework import status

from tests.factories import MilestoneFactory, TaskFactory, WorkplanFactory


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Pagination Test Workplan")


@pytest.fixture
def milestone(db, workplan):
    return MilestoneFactory(name="Pagination Test Phase", workplan=workplan)


@pytest.mark.django_db
class TestCursorPagination:
    def test_first_page_has_page_size_items(self, api_client, milestone, workplan):
        """Create 60 tasks; first page should return 50."""
        for i in range(60):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        response = api_client.get("/v1/tasks/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 50

    def test_first_page_has_next_cursor(self, api_client, milestone, workplan):
        """With 60 items and page_size=50, first page should have a next cursor."""
        for i in range(60):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        response = api_client.get("/v1/tasks/")
        assert response.data["next"] is not None

    def test_first_page_has_no_previous_cursor(self, api_client, milestone, workplan):
        """First page should have no previous cursor."""
        for i in range(60):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        response = api_client.get("/v1/tasks/")
        assert response.data["previous"] is None

    def test_following_next_cursor_returns_remaining_items(self, api_client, milestone, workplan):
        """Following the next cursor should return the remaining 10 items."""
        for i in range(60):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        first_response = api_client.get("/v1/tasks/")
        next_url = first_response.data["next"]
        assert next_url is not None

        second_response = api_client.get(next_url)
        assert second_response.status_code == status.HTTP_200_OK
        assert len(second_response.data["results"]) == 10

    def test_second_page_has_no_next_cursor(self, api_client, milestone, workplan):
        """Second page (last page) should have no next cursor."""
        for i in range(60):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        first_response = api_client.get("/v1/tasks/")
        next_url = first_response.data["next"]

        second_response = api_client.get(next_url)
        assert second_response.data["next"] is None

    def test_second_page_has_previous_cursor(self, api_client, milestone, workplan):
        """Second page should have a previous cursor."""
        for i in range(60):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        first_response = api_client.get("/v1/tasks/")
        next_url = first_response.data["next"]

        second_response = api_client.get(next_url)
        assert second_response.data["previous"] is not None

    def test_custom_page_size_via_query_param(self, api_client, milestone, workplan):
        """Verify ?page_size=10 returns 10 items."""
        for i in range(20):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        response = api_client.get("/v1/tasks/?page_size=10")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 10

    def test_all_items_covered_across_pages(self, api_client, milestone, workplan):
        """All 60 items should appear exactly once across two pages."""
        for i in range(60):
            TaskFactory(title=f"Task {i}", milestone=milestone, workplan=workplan)
        first_response = api_client.get("/v1/tasks/")
        next_url = first_response.data["next"]
        second_response = api_client.get(next_url)

        first_ids = {item["id"] for item in first_response.data["results"]}
        second_ids = {item["id"] for item in second_response.data["results"]}

        # No overlap
        assert len(first_ids & second_ids) == 0
        # Total coverage
        assert len(first_ids | second_ids) == 60

    def test_response_has_pagination_keys(self, api_client, milestone, workplan):
        """List response should always contain next, previous, results keys."""
        response = api_client.get("/v1/tasks/")
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data
