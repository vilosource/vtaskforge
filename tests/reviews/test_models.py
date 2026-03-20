"""
Tests for Review model.
"""
import pytest

from reviews.models import Review
from tests.factories import PhaseFactory, ReviewFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def phase(db, workplan):
    return PhaseFactory(name="Test Phase", workplan=workplan)


@pytest.fixture
def task(db, phase, workplan):
    return TaskFactory(
        title="Test Task",
        phase=phase,
        workplan=workplan,
        status="pending_start_review",
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewModel:
    def test_create_review(self, task):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer_id="user-1",
        )
        assert review.id is not None
        assert len(review.id) == 21
        assert review.task == task
        assert review.decision == "approved"
        assert review.reviewer_id == "user-1"
        assert review.reviewer_type == "human"
        assert review.reason == ""
        assert review.created_at is not None
        assert review.updated_at is not None

    def test_default_reviewer_type_is_human(self, task):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer_id="user-1",
        )
        assert review.reviewer_type == "human"

    def test_agent_reviewer_type(self, task):
        review = ReviewFactory(
            task=task,
            decision="rejected",
            reviewer_id="agent-1",
            reviewer_type="agent",
        )
        assert review.reviewer_type == "agent"

    def test_reason_optional(self, task):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer_id="user-1",
        )
        assert review.reason == ""

    def test_reason_can_be_set(self, task):
        review = ReviewFactory(
            task=task,
            decision="changes_requested",
            reviewer_id="user-1",
            reason="Needs more detail",
        )
        assert review.reason == "Needs more detail"

    def test_cascade_delete(self, task):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer_id="user-1",
        )
        review_id = review.id
        task.delete()
        assert not Review.objects.filter(id=review_id).exists()

    def test_ordering_ascending(self, task):
        review1 = ReviewFactory(task=task, decision="approved", reviewer_id="user-1")
        review2 = ReviewFactory(task=task, decision="rejected", reviewer_id="user-2")
        reviews = list(Review.objects.filter(task=task))
        assert reviews[0].id == review1.id
        assert reviews[1].id == review2.id

    def test_str_representation(self, task):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer_id="user-1",
        )
        assert "approved" in str(review)
        assert "user-1" in str(review)
