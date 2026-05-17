"""R2 — fleet principal authorization (vafi#18, Bet B / scope S1).

A fleet service principal (UserProfile.user_type='service') is authorised
by role across the whole instance with NO ProjectMembership row; humans
unchanged. See docs/fleet-principal-authorization-DESIGN.md.
"""

import pytest
from django.contrib.auth.models import User, AnonymousUser
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from prefs.models import UserProfile, ProjectMembership
from core.authorization import (
    is_fleet_principal,
    check_project_membership,
    require_project_membership,
    scope_queryset_to_user_projects,
    RoleBasedPermission,
)
from tasks.models import Task
from tasks.services import claim_task
from events.models import TaskEvent
from tests.factories import ProjectFactory, TaskFactory, AgentFactory


def _svc(username="svc1"):
    u = User.objects.create_user(username)  # no password → non-human
    UserProfile.objects.create(user=u, user_type="service")
    return u


def _human(username="h1"):
    u = User.objects.create_user(username, password="pw")
    UserProfile.objects.create(user=u, user_type="human")
    return u


def _req(user, method):
    return type("R", (), {"user": user, "method": method})()


@pytest.mark.django_db
class TestIsFleetPrincipal:
    def test_service_profile_is_fleet(self):
        assert is_fleet_principal(_svc()) is True

    def test_human_is_not_fleet(self):
        assert is_fleet_principal(_human()) is False

    def test_no_profile_is_not_fleet(self):
        assert is_fleet_principal(User.objects.create_user("noprof")) is False

    def test_agent_type_is_not_service(self):
        u = User.objects.create_user("ag")
        UserProfile.objects.create(user=u, user_type="agent")
        assert is_fleet_principal(u) is False

    def test_unauthenticated_is_not_fleet(self):
        assert is_fleet_principal(AnonymousUser()) is False


@pytest.mark.django_db
class TestGatesFleetPrincipalNoMembership:
    def test_check_membership_true_without_row(self):
        u, p = _svc(), ProjectFactory()
        assert ProjectMembership.objects.filter(user=u).count() == 0
        assert check_project_membership(u, p.id) is True

    def test_require_membership_no_raise(self):
        require_project_membership(_svc(), ProjectFactory().id)

    def test_scope_queryset_sees_all(self):
        u = _svc()
        t = TaskFactory()
        assert t in scope_queryset_to_user_projects(Task.objects.all(), u, Task)

    def test_human_nonmember_still_denied(self):
        u, p = _human(), ProjectFactory()
        assert check_project_membership(u, p.id) is False
        with pytest.raises(PermissionDenied):
            require_project_membership(u, p.id)


@pytest.mark.django_db
class TestRoleBasedFleetBounded:
    def _perm(self, user, method, task):
        return RoleBasedPermission().has_object_permission(_req(user, method), None, task)

    def test_safe_allowed(self):
        assert self._perm(_svc(), "GET", TaskFactory()) is True

    def test_delete_denied(self):
        assert self._perm(_svc(), "DELETE", TaskFactory()) is False

    def test_patch_own_claimed_allowed(self):
        u = _svc()
        assert self._perm(u, "PATCH", TaskFactory(claimed_by=u)) is True

    def test_patch_unowned_denied(self):
        other = _human("other")
        assert self._perm(_svc(), "PATCH", TaskFactory(created_by=other)) is False


@pytest.mark.django_db
class TestRegistrationActivatesService:
    def test_agent_registration_sets_service_profile(self):
        c = APIClient()
        r = c.post("/v1/agents/", {"name": "fleet-exec-x", "tags": ["executor"]}, format="json")
        assert r.status_code in (200, 201), r.content
        from agents.models import Agent
        a = Agent.objects.get(name="fleet-exec-x")
        assert a.user is not None
        assert a.user.profile.user_type == "service"


@pytest.mark.django_db
class TestClaimNoLongerAutoAddsMembership:
    def test_claim_does_not_create_membership_or_event(self):
        agent = AgentFactory()  # link_user post-gen creates agent.user
        task = TaskFactory(status="todo")
        claim_task(task.id, agent.id, agent.tags or [])
        assert ProjectMembership.objects.filter(user=agent.user).count() == 0
        assert not TaskEvent.objects.filter(
            task=task, event_type="auto_membership_grant"
        ).exists()
