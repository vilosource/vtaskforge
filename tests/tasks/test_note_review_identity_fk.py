"""TDD tests for Note.actor and Review.reviewer FK migration (Phase 0, Step 4).

Renames actor_id → actor (FK User), reviewer_id → reviewer (FK User).
v1 serializers preserve old field names for backward compat.

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Step 4 DoD.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from tasks.models import Note, Task
from reviews.models import Review
from tests.factories import AgentFactory, TaskFactory, MilestoneFactory


@pytest.fixture
def staff_user(db):
    user = User.objects.create_user("staffuser", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return user, client


@pytest.fixture
def todo_task(db):
    return TaskFactory(status="todo")


# ---------------------------------------------------------------------------
# Note.actor FK
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestNoteActorFK:

    def test_note_create_sets_actor(self, staff_user, todo_task):
        """POST note sets actor to request.user."""
        user, client = staff_user
        response = client.post(
            f"/v1/tasks/{todo_task.id}/notes/",
            {"text": "Test note"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        note = Note.objects.get(id=response.data["id"])
        assert note.actor == user

    def test_note_actor_not_writable(self, staff_user, todo_task):
        """Client cannot override actor — server always sets it."""
        user, client = staff_user
        hacker = User.objects.create_user("hacker")
        response = client.post(
            f"/v1/tasks/{todo_task.id}/notes/",
            {"text": "Test note", "actor_id": hacker.username},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        note = Note.objects.get(id=response.data["id"])
        assert note.actor == user  # Server-set, not hacker

    def test_v1_note_serializer_actor_id(self, staff_user, todo_task):
        """GET note returns actor_id as username string for v1 compat."""
        user, client = staff_user
        Note.objects.create(task=todo_task, text="Test", actor=user)

        response = client.get(f"/v1/tasks/{todo_task.id}/notes/")
        assert response.status_code == 200
        note_data = response.data["results"][0]
        assert "actor_id" in note_data
        assert note_data["actor_id"] == user.username

    def test_note_data_migration_semantics(self):
        """Note with actor FK set works correctly."""
        user = User.objects.create_user("note-actor")
        task = TaskFactory()
        note = Note.objects.create(task=task, text="Test", actor=user)
        note.refresh_from_db()
        assert note.actor == user
        assert note.actor_id == user.id


# ---------------------------------------------------------------------------
# Review.reviewer FK
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewReviewerFK:

    def test_review_submit_sets_reviewer(self, staff_user, todo_task):
        """Submit review sets reviewer to the reviewer User."""
        user, client = staff_user
        # Put task in review state
        todo_task.status = "pending_completion_review"
        todo_task.save(update_fields=["status"])

        response = client.post(
            f"/v1/tasks/{todo_task.id}/reviews/",
            {"decision": "approved", "reason": "looks good"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        review = Review.objects.get(task=todo_task)
        assert review.reviewer == user

    def test_v1_review_serializer_reviewer_id(self, staff_user, todo_task):
        """GET review returns reviewer_id as username string for v1 compat."""
        user, client = staff_user
        Review.objects.create(
            task=todo_task, decision="approved", reason="ok",
            reviewer=user, reviewer_type="human",
        )

        response = client.get(f"/v1/tasks/{todo_task.id}/reviews/")
        assert response.status_code == 200
        review_data = response.data["results"][0]
        assert "reviewer_id" in review_data
        assert review_data["reviewer_id"] == user.username

    def test_review_data_migration_semantics(self):
        """Review with reviewer FK set works correctly."""
        user = User.objects.create_user("reviewer-user")
        task = TaskFactory()
        review = Review.objects.create(
            task=task, decision="approved", reason="ok",
            reviewer=user, reviewer_type="human",
        )
        review.refresh_from_db()
        assert review.reviewer == user
        assert review.reviewer_id == user.id
