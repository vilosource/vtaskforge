"""
Tests for GET /v2/reviews/pending/ — cross-project judge-poll endpoint.

Regression test for vtaskforge#6: judge agents could not see review
work because list-by-status applied generic project-membership scoping
and silently returned empty for users who weren't members. The new
endpoint deliberately ignores membership.
"""
import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from tests.factories import MilestoneFactory, TaskFactory, WorkplanFactory


PENDING_URL = "/v2/reviews/pending/"


@pytest.fixture
def non_member_client(db):
    """Authenticated user with no project memberships and is_staff=False."""
    client = APIClient()
    user = User.objects.create_user(username="judge-agent-user", password="x")
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test WP")


@pytest.fixture
def milestone(db, workplan):
    return MilestoneFactory(name="Test MS", workplan=workplan)


@pytest.fixture
def pending_judged_task(db, milestone, workplan):
    return TaskFactory(
        title="Awaiting judge",
        milestone=milestone,
        workplan=workplan,
        status="pending_completion_review",
        judge=True,
    )


@pytest.fixture
def pending_unjudged_task(db, milestone, workplan):
    return TaskFactory(
        title="Awaiting auto-complete (no judge)",
        milestone=milestone,
        workplan=workplan,
        status="pending_completion_review",
        judge=False,
    )


@pytest.fixture
def doing_task(db, milestone, workplan):
    return TaskFactory(
        title="In progress",
        milestone=milestone,
        workplan=workplan,
        status="doing",
        judge=True,
    )


@pytest.mark.django_db
class TestPendingReviewsEndpoint:
    """The fleet-wide judge-poll endpoint — replaces the broken /v1 list path."""

    def test_v2_path_exists(self, api_client):
        response = api_client.get(PENDING_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_v1_path_does_not_exist(self, api_client):
        """v2-only by design (Phase 5 v1 deprecation)."""
        response = api_client.get("/v1/reviews/pending/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_pending_judged_task(self, api_client, pending_judged_task):
        response = api_client.get(PENDING_URL)
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        assert pending_judged_task.id in ids

    def test_excludes_unjudged_pending_completion(self, api_client, pending_judged_task, pending_unjudged_task):
        response = api_client.get(PENDING_URL)
        ids = [t["id"] for t in response.data["results"]]
        assert pending_judged_task.id in ids
        assert pending_unjudged_task.id not in ids

    def test_excludes_other_statuses(self, api_client, pending_judged_task, doing_task):
        response = api_client.get(PENDING_URL)
        ids = [t["id"] for t in response.data["results"]]
        assert pending_judged_task.id in ids
        assert doing_task.id not in ids

    def test_visible_to_non_member_judge_user(self, non_member_client, pending_judged_task):
        """Regression for vtaskforge#6.

        A user with no project memberships must still see fleet-wide
        review work. The /v1/tasks/?status=... endpoint hides this
        behind scope_queryset_to_user_projects; this endpoint must not.
        """
        response = non_member_client.get(PENDING_URL)
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        assert pending_judged_task.id in ids, (
            "Non-member judge agent must still see review work — "
            "this is the whole point of the dedicated endpoint."
        )

    def test_unauthenticated_rejected(self, unauthenticated_client):
        response = unauthenticated_client.get(PENDING_URL)
        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
