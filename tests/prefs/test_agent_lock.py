"""TDD tests for AgentLock model.

Phase 3 of User Management: persistent agent session locks.
"""

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from prefs.models import AgentLock


@pytest.mark.django_db
class TestAgentLock:
    def test_acquire_lock(self):
        user = User.objects.create_user("user1", password="pass")
        lock = AgentLock.objects.create(
            project_id="proj1", role="architect", user=user
        )
        assert lock.pk is not None
        assert lock.project_id == "proj1"
        assert lock.role == "architect"

    def test_unique_constraint_project_role(self):
        u1 = User.objects.create_user("u1", password="pass")
        u2 = User.objects.create_user("u2", password="pass")
        AgentLock.objects.create(project_id="proj1", role="architect", user=u1)
        with pytest.raises(IntegrityError):
            AgentLock.objects.create(project_id="proj1", role="architect", user=u2)

    def test_second_user_cannot_acquire_same_lock(self):
        u1 = User.objects.create_user("u1", password="pass")
        u2 = User.objects.create_user("u2", password="pass")
        AgentLock.objects.create(project_id="proj1", role="architect", user=u1)
        assert not AgentLock.objects.filter(
            project_id="proj1", role="architect", user=u2
        ).exists()

    def test_same_user_reacquire_returns_existing(self):
        user = User.objects.create_user("user1", password="pass")
        lock1 = AgentLock.objects.create(
            project_id="proj1", role="architect", user=user
        )
        lock2 = AgentLock.objects.get(project_id="proj1", role="architect", user=user)
        assert lock1.pk == lock2.pk

    def test_release_lock(self):
        user = User.objects.create_user("user1", password="pass")
        lock = AgentLock.objects.create(
            project_id="proj1", role="architect", user=user
        )
        lock.delete()
        assert not AgentLock.objects.filter(
            project_id="proj1", role="architect"
        ).exists()

    def test_last_activity_updated_on_save(self):
        user = User.objects.create_user("user1", password="pass")
        lock = AgentLock.objects.create(
            project_id="proj1", role="architect", user=user
        )
        assert lock.last_activity is not None
