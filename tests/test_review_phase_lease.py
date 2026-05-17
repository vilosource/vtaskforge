"""R3 — review-phase lease + reaper (the I2 backstop for vafi#18).

A task in pending_completion_review whose verdict is never recorded must
not stall forever: it gets a deadline on entry and a server-side reaper
escalates it to needs_attention. See docs/review-phase-lease-DESIGN.md.
"""

import pytest
from datetime import timedelta
from django.utils import timezone

from tasks.models import Task
from tasks.state_machine import get_valid_transitions, perform_transition
from tasks.celery_tasks import expire_stale_reviews, expire_stale_claims
from events.models import TaskEvent
from tests.factories import TaskFactory


@pytest.mark.django_db
class TestReviewStateMachineEdge:
    def test_pcr_to_needs_attention_is_valid(self):
        assert "needs_attention" in get_valid_transitions("pending_completion_review")

    def test_pcr_existing_transitions_unchanged(self):
        v = get_valid_transitions("pending_completion_review")
        assert {"done", "changes_requested", "cancelled"}.issubset(set(v))


@pytest.mark.django_db
class TestReviewLeaseSetOnEntry:
    def test_entering_pcr_sets_review_expires_at(self):
        t = TaskFactory(status="doing")
        assert t.review_expires_at is None
        perform_transition(t, "pending_completion_review")
        t.refresh_from_db()
        assert t.review_expires_at is not None
        assert t.review_expires_at > timezone.now()


@pytest.mark.django_db
class TestExpireStaleReviews:
    def _pcr(self, expires_delta):
        t = TaskFactory(status="pending_completion_review")
        t.review_expires_at = timezone.now() + expires_delta
        t.save(update_fields=["review_expires_at"])
        return t

    def test_expired_review_escalates_to_needs_attention(self):
        t = self._pcr(timedelta(minutes=-1))
        n = expire_stale_reviews()
        t.refresh_from_db()
        assert n >= 1
        assert t.status == "needs_attention"
        assert TaskEvent.objects.filter(task=t, event_type="review_expired").exists()

    def test_future_deadline_untouched(self):
        t = self._pcr(timedelta(minutes=30))
        expire_stale_reviews()
        t.refresh_from_db()
        assert t.status == "pending_completion_review"

    def test_no_crosstalk_with_claim_reaper(self):
        # a stale review is NOT reaped by expire_stale_claims
        t = self._pcr(timedelta(minutes=-1))
        expire_stale_claims()
        t.refresh_from_db()
        assert t.status == "pending_completion_review"
        # a stale doing claim is NOT reaped by expire_stale_reviews
        d = TaskFactory(status="doing")
        d.claim_expires_at = timezone.now() - timedelta(minutes=1)
        d.save(update_fields=["claim_expires_at"])
        expire_stale_reviews()
        d.refresh_from_db()
        assert d.status == "doing"
