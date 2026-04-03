"""
Tests for the expire_stale_claims Celery task.
"""
import pytest
from datetime import timedelta
from unittest.mock import patch, call

from django.utils import timezone

from events.models import TaskEvent
from tasks.celery_tasks import expire_stale_claims
from tasks.models import Task
from tests.factories import TaskFactory


@pytest.mark.django_db
class TestExpireStaleClaims:
    def _make_claimed_task(self, claimed_by="agent-1", offset_seconds=-10):
        """Helper: create a 'doing' task with claim_expires_at relative to now."""
        now = timezone.now()
        task = TaskFactory(
            status="doing",
            claimed_by=claimed_by,
            claimed_at=now - timedelta(hours=1),
            claim_expires_at=now + timedelta(seconds=offset_seconds),
        )
        return task

    def test_expired_task_moves_to_needs_attention(self):
        """An expired claim should move the task to needs_attention."""
        task = self._make_claimed_task(offset_seconds=-10)
        expire_stale_claims()
        task.refresh_from_db()
        assert task.status == "needs_attention"

    def test_future_claim_not_affected(self):
        """A task whose claim hasn't expired yet should remain in 'doing'."""
        task = self._make_claimed_task(offset_seconds=3600)
        expire_stale_claims()
        task.refresh_from_db()
        assert task.status == "doing"

    def test_doing_task_without_claim_expires_at_not_affected(self):
        """A doing task with no claim_expires_at should not be touched."""
        task = TaskFactory(status="doing", claimed_by="agent-1", claim_expires_at=None)
        expire_stale_claims()
        task.refresh_from_db()
        assert task.status == "doing"

    def test_non_doing_task_not_affected(self):
        """Tasks not in 'doing' status should not be expired even if claim_expires_at is past."""
        now = timezone.now()
        task = TaskFactory(
            status="todo",
            claimed_by="agent-1",
            claim_expires_at=now - timedelta(seconds=10),
        )
        expire_stale_claims()
        task.refresh_from_db()
        assert task.status == "todo"

    def test_claim_fields_cleared(self):
        """All claim fields should be cleared after expiry."""
        task = self._make_claimed_task()
        expire_stale_claims()
        task.refresh_from_db()
        assert task.claimed_by is None
        assert task.claimed_at is None
        assert task.claim_expires_at is None

    def test_task_event_created_with_claim_expired_type(self):
        """A TaskEvent with event_type='claim_expired' should be created."""
        task = self._make_claimed_task(claimed_by="agent-42")
        expire_stale_claims()
        events = TaskEvent.objects.filter(task=task, event_type="claim_expired")
        assert events.count() == 1
        event = events.first()
        assert event.data["previous_agent"] == "agent-42"
        assert event.trigger_source == "system"

    def test_returns_count(self):
        """expire_stale_claims should return the number of tasks expired."""
        self._make_claimed_task()
        self._make_claimed_task()
        # one task whose claim is not yet expired
        self._make_claimed_task(offset_seconds=3600)
        result = expire_stale_claims()
        assert result == 2

    def test_returns_zero_when_nothing_expired(self):
        """Returns 0 when no tasks are expired."""
        result = expire_stale_claims()
        assert result == 0

    def test_idempotent(self):
        """Running the task twice should not double-expire or create duplicate events."""
        task = self._make_claimed_task()
        expire_stale_claims()
        expire_stale_claims()
        task.refresh_from_db()
        assert task.status == "needs_attention"
        assert TaskEvent.objects.filter(task=task, event_type="claim_expired").count() == 1

    def test_expire_creates_event_via_service(self):
        """expire_stale_claims must use EventService (record_event) to create the claim_expired event."""
        task = self._make_claimed_task(claimed_by="agent-99")
        with patch("tasks.celery_tasks.record_event") as mock_record_event:
            expire_stale_claims()
        # record_event must be called with the claim_expired event type
        calls = mock_record_event.call_args_list
        claim_expired_calls = [
            c for c in calls
            if len(c.args) >= 2 and c.args[1] == "claim_expired"
        ]
        assert len(claim_expired_calls) == 1
        _, kwargs = claim_expired_calls[0].args, claim_expired_calls[0].kwargs
        assert claim_expired_calls[0].args[0].pk == task.pk
        assert claim_expired_calls[0].kwargs.get("trigger_source") == "system"

    def test_expire_uses_state_machine(self):
        """expire_stale_claims must use perform_transition (not direct status assignment) for status changes."""
        task = self._make_claimed_task()
        with patch("tasks.celery_tasks.perform_transition") as mock_transition:
            expire_stale_claims()
        mock_transition.assert_called_once()
        args = mock_transition.call_args
        assert args.args[0].pk == task.pk
        assert args.args[1] == "needs_attention"
        assert args.kwargs.get("trigger_source") == "system"

    def test_expired_with_frozen_time(self):
        """Verify expiry logic using mocked timezone.now."""
        now = timezone.now()
        future = now + timedelta(hours=1)
        # Create a task that will expire at 'future'
        task = TaskFactory(
            status="doing",
            claimed_by="agent-frozen",
            claimed_at=now,
            claim_expires_at=future,
        )
        # At 'now' the task should NOT expire
        with patch("tasks.celery_tasks.timezone") as mock_tz:
            mock_tz.now.return_value = now
            result = expire_stale_claims()
        assert result == 0
        task.refresh_from_db()
        assert task.status == "doing"

        # Past the expiry time, it SHOULD expire
        past_expiry = future + timedelta(seconds=1)
        with patch("tasks.celery_tasks.timezone") as mock_tz:
            mock_tz.now.return_value = past_expiry
            result = expire_stale_claims()
        assert result == 1
        task.refresh_from_db()
        assert task.status == "needs_attention"
