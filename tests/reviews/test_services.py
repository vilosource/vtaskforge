"""
Unit tests for reviews.services.submit_review().
"""
import pytest

from reviews.models import Review
from reviews.services import ReviewError, submit_review
from tests.factories import MilestoneFactory, TaskFactory, WorkplanFactory


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
def task_pending_start(db, milestone, workplan):
    return TaskFactory(
        title="Start Review Task",
        milestone=milestone,
        workplan=workplan,
        status="pending_start_review",
    )


@pytest.fixture
def task_pending_completion(db, milestone, workplan):
    return TaskFactory(
        title="Completion Review Task",
        milestone=milestone,
        workplan=workplan,
        status="pending_completion_review",
    )


@pytest.fixture
def task_todo(db, milestone, workplan):
    return TaskFactory(
        title="Todo Task",
        milestone=milestone,
        workplan=workplan,
        status="todo",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_submit_review_approved_start_review(task_pending_start):
    """approved + pending_start_review transitions task to todo."""
    result = submit_review(
        task_id=task_pending_start.id,
        decision="approved",
        reviewer_id="user-1",
    )
    task_pending_start.refresh_from_db()
    assert task_pending_start.status == "todo"
    assert result["previous_status"] == "pending_start_review"
    assert result["task"].id == task_pending_start.id


@pytest.mark.django_db
def test_submit_review_approved_completion_review(task_pending_completion):
    """approved + pending_completion_review transitions task to done."""
    result = submit_review(
        task_id=task_pending_completion.id,
        decision="approved",
        reviewer_id="user-1",
    )
    task_pending_completion.refresh_from_db()
    assert task_pending_completion.status == "done"
    assert result["previous_status"] == "pending_completion_review"


@pytest.mark.django_db
def test_submit_review_changes_requested(task_pending_start):
    """changes_requested sets review_return_to and transitions to changes_requested."""
    result = submit_review(
        task_id=task_pending_start.id,
        decision="changes_requested",
        reviewer_id="user-1",
        reason="Needs more work",
    )
    task_pending_start.refresh_from_db()
    assert task_pending_start.status == "changes_requested"
    assert task_pending_start.review_return_to == "pending_start_review"
    assert result["previous_status"] == "pending_start_review"


@pytest.mark.django_db
def test_submit_review_not_in_review_status_raises(task_todo):
    """Raises ReviewError when task is not in a review status."""
    with pytest.raises(ReviewError) as exc_info:
        submit_review(
            task_id=task_todo.id,
            decision="approved",
            reviewer_id="user-1",
        )
    assert exc_info.value.status_code == 400
    assert "todo" in exc_info.value.message


@pytest.mark.django_db
def test_submit_review_creates_review_record(task_pending_start):
    """submit_review creates a Review record with correct fields."""
    submit_review(
        task_id=task_pending_start.id,
        decision="approved",
        reviewer_id="reviewer-42",
        reviewer_type="agent",
        reason="Looks good",
    )
    review = Review.objects.get(task=task_pending_start, decision="approved")
    assert review.reviewer_id == "reviewer-42"
    assert review.reviewer_type == "agent"
    assert review.reason == "Looks good"
