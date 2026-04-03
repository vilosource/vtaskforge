"""
Tests for Review model.
"""
import pytest
from django.contrib.auth.models import User

from reviews.models import Review
from tests.factories import MilestoneFactory, ReviewFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def milestone(db, workplan):
    return MilestoneFactory(name="Test Phase", workplan=workplan)


@pytest.fixture
def task(db, milestone, workplan):
    return TaskFactory(
        title="Test Task",
        milestone=milestone,
        workplan=workplan,
        status="pending_start_review",
    )


@pytest.fixture
def reviewer_user(db):
    return User.objects.create_user(username="user-1")


@pytest.fixture
def reviewer_user_2(db):
    return User.objects.create_user(username="user-2")


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReviewModel:
    def test_create_review(self, task, reviewer_user):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer=reviewer_user,
        )
        assert review.id is not None
        assert len(review.id) == 21
        assert review.task == task
        assert review.decision == "approved"
        assert review.reviewer == reviewer_user
        assert review.reviewer.username == "user-1"
        assert review.reviewer_type == "human"
        assert review.reason == ""
        assert review.created_at is not None
        assert review.updated_at is not None

    def test_default_reviewer_type_is_human(self, task, reviewer_user):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer=reviewer_user,
        )
        assert review.reviewer_type == "human"

    def test_agent_reviewer_type(self, task):
        agent_user = User.objects.create_user(username="agent-1")
        review = ReviewFactory(
            task=task,
            decision="rejected",
            reviewer=agent_user,
            reviewer_type="agent",
        )
        assert review.reviewer_type == "agent"

    def test_reason_optional(self, task, reviewer_user):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer=reviewer_user,
        )
        assert review.reason == ""

    def test_reason_can_be_set(self, task, reviewer_user):
        review = ReviewFactory(
            task=task,
            decision="changes_requested",
            reviewer=reviewer_user,
            reason="Needs more detail",
        )
        assert review.reason == "Needs more detail"

    def test_cascade_delete(self, task, reviewer_user):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer=reviewer_user,
        )
        review_id = review.id
        task.delete()
        assert not Review.objects.filter(id=review_id).exists()

    def test_ordering_ascending(self, task, reviewer_user, reviewer_user_2):
        review1 = ReviewFactory(task=task, decision="approved", reviewer=reviewer_user)
        review2 = ReviewFactory(task=task, decision="rejected", reviewer=reviewer_user_2)
        reviews = list(Review.objects.filter(task=task))
        assert reviews[0].id == review1.id
        assert reviews[1].id == review2.id

    def test_str_representation(self, task, reviewer_user):
        review = ReviewFactory(
            task=task,
            decision="approved",
            reviewer=reviewer_user,
        )
        assert "approved" in str(review)
        assert "user-1" in str(review)
