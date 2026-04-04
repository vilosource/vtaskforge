"""Step 6: v2 Review serializer tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from tasks.models import Task
    from reviews.models import Review
    from prefs.models import ProjectMembership

    user = User.objects.create_user("revv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="RevProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    task = Task.objects.create(title="RevTask", project=project, created_by=user, status="pending_completion_review")
    review = Review.objects.create(task=task, decision="approved", reason="LGTM", reviewer=user, reviewer_type="human")

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, task, review


class TestReviewV2:
    def test_v2_review_reviewer_is_actor_ref(self, setup):
        """DoD #4"""
        client, task, review = setup
        resp = client.get(f"/v2/tasks/{task.id}/reviews/")
        assert resp.status_code == 200
        rev = resp.data["results"][0]
        assert isinstance(rev["reviewer"], dict)
        assert rev["reviewer"]["type"] == "user"

    def test_v2_review_task_is_task_ref(self, setup):
        """DoD #5"""
        client, task, review = setup
        resp = client.get(f"/v2/tasks/{task.id}/reviews/")
        rev = resp.data["results"][0]
        assert isinstance(rev["task"], dict)
        assert rev["task"]["id"] == task.id

    def test_v2_review_no_legacy_reviewer_id(self, setup):
        """DoD #6"""
        client, task, review = setup
        resp = client.get(f"/v2/tasks/{task.id}/reviews/")
        rev = resp.data["results"][0]
        assert "reviewer_id" not in rev

    def test_v1_review_still_has_reviewer_id(self, setup):
        """DoD #7"""
        client, task, review = setup
        resp = client.get(f"/v1/tasks/{task.id}/reviews/")
        rev = resp.data["results"][0]
        assert "reviewer_id" in rev
        assert isinstance(rev["reviewer_id"], str)
