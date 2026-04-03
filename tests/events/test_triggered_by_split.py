"""TDD tests for TaskEvent.triggered_by → trigger_source + actor split (Phase 0, Step 2).

The triggered_by CharField conflated identity (who) with action labels (what).
This step splits it into:
- trigger_source: CharField for action labels ("claim", "submit", "system")
- actor: FK User for identity (who triggered the event, null for system events)

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Step 2 DoD.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from events.models import TaskEvent
from events.services import record_event
from tests.factories import TaskFactory, AgentFactory


@pytest.fixture
def user(db):
    return User.objects.create_user("testuser", password="pass")


@pytest.fixture
def agent_user(db):
    agent = AgentFactory(name="test-executor")
    return agent.user


@pytest.fixture
def task(db):
    return TaskFactory()


# ---------------------------------------------------------------------------
# record_event() new signature
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRecordEventNewSignature:

    def test_record_event_with_actor(self, task, user):
        """record_event with actor=user sets both trigger_source and actor FK."""
        event = record_event(
            task, "claimed",
            data={"agent_id": "test"},
            trigger_source="claim",
            actor=user,
        )
        assert event is not None
        assert event.trigger_source == "claim"
        assert event.actor == user
        assert event.actor_id == user.id

    def test_record_event_system_no_actor(self, task):
        """System events have trigger_source but no actor."""
        event = record_event(
            task, "claim_expired",
            data={"previous_agent": "agent-1"},
            trigger_source="system",
        )
        assert event is not None
        assert event.trigger_source == "system"
        assert event.actor is None


# ---------------------------------------------------------------------------
# perform_transition() passes actor through
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPerformTransitionActor:

    def test_perform_transition_passes_actor(self, user):
        """perform_transition creates an event with the actor FK set."""
        from tasks.state_machine import perform_transition

        task = TaskFactory(status="draft")
        perform_transition(task, "todo", trigger_source="submit", actor=user)

        event = TaskEvent.objects.filter(task=task, event_type="status_changed").first()
        assert event is not None
        assert event.trigger_source == "submit"
        assert event.actor == user


# ---------------------------------------------------------------------------
# v1 serializer backward compatibility
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestV1SerializerCompat:

    def test_v1_serializer_compat_actor(self, task, user):
        """v1 serializer returns triggered_by as username string when actor is set."""
        from events.serializers import TaskEventSerializer

        event = record_event(
            task, "claimed",
            trigger_source="claim",
            actor=user,
        )
        data = TaskEventSerializer(event).data
        assert "triggered_by" in data
        assert data["triggered_by"] == user.username

    def test_v1_serializer_compat_system(self, task):
        """v1 serializer returns triggered_by as trigger_source when no actor."""
        from events.serializers import TaskEventSerializer

        event = record_event(
            task, "claim_expired",
            trigger_source="system",
        )
        data = TaskEventSerializer(event).data
        assert data["triggered_by"] == "system"


# ---------------------------------------------------------------------------
# Celery task uses new signature
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCeleryNewSignature:

    def test_celery_expire_claims_uses_new_signature(self, settings):
        """expire_stale_claims creates events with trigger_source='system', actor=None."""
        from datetime import timedelta
        from django.utils import timezone
        from tasks.celery_tasks import expire_stale_claims

        settings.CELERY_TASK_ALWAYS_EAGER = True
        settings.CELERY_TASK_EAGER_PROPAGATES = True

        task = TaskFactory(
            status="doing",
            claimed_by="agent-1",
            claimed_at=timezone.now() - timedelta(hours=2),
            claim_expires_at=timezone.now() - timedelta(hours=1),
        )

        expire_stale_claims()

        event = TaskEvent.objects.filter(
            task=task, event_type="claim_expired"
        ).first()
        assert event is not None
        assert event.trigger_source == "system"
        assert event.actor is None


# ---------------------------------------------------------------------------
# Data migration correctness (tested via model state, not migration runner)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDataMigrationLogic:
    """These test the resolution logic that the data migration uses.
    The actual migration is tested via integration (migrate on real DB).
    Here we verify the field semantics on the new model.
    """

    def test_agent_id_stored_as_actor(self, task, agent_user):
        """An event created with an agent actor has both fields set."""
        event = TaskEvent.objects.create(
            task=task,
            event_type="claimed",
            data={"agent_id": agent_user.username},
            trigger_source="claim",
            actor=agent_user,
        )
        event.refresh_from_db()
        assert event.actor == agent_user
        assert event.trigger_source == "claim"

    def test_action_label_no_actor(self, task):
        """An event with only an action label has no actor."""
        event = TaskEvent.objects.create(
            task=task,
            event_type="status_changed",
            data={"from": "draft", "to": "todo"},
            trigger_source="submit",
            actor=None,
        )
        event.refresh_from_db()
        assert event.actor is None
        assert event.trigger_source == "submit"

    def test_empty_trigger_source_allowed(self, task):
        """Both fields can be empty/null (legacy data)."""
        event = TaskEvent.objects.create(
            task=task,
            event_type="status_changed",
            data={},
            trigger_source="",
            actor=None,
        )
        event.refresh_from_db()
        assert event.trigger_source == ""
        assert event.actor is None
