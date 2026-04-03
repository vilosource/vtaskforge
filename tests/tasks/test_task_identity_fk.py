"""TDD tests for Task identity field migration (Phase 0, Step 3).

Converts assigned_to, claimed_by, created_by from CharField to FK User.

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Step 3 DoD.
"""

import pytest
from django.contrib.auth.models import User
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from agents.models import Agent
from tasks.models import Task
from tests.factories import AgentFactory, TaskFactory, MilestoneFactory, WorkplanFactory


@pytest.fixture
def staff_user(db):
    user = User.objects.create_user("staffuser", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return user, client


@pytest.fixture
def agent_with_user(db):
    return AgentFactory(name="test-executor")


@pytest.fixture
def workplan(db):
    return WorkplanFactory()


@pytest.fixture
def milestone(workplan):
    return MilestoneFactory(workplan=workplan)


# ---------------------------------------------------------------------------
# claim_task() sets FK
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestClaimSetsFK:

    def test_claim_sets_user_fk(self, staff_user, agent_with_user, milestone):
        user, client = staff_user
        agent = agent_with_user
        task = TaskFactory(status="todo", milestone=milestone)

        response = client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent.id},
            format="json",
        )
        assert response.status_code == 200

        task.refresh_from_db()
        assert task.claimed_by == agent.user
        assert task.claimed_by_id == agent.user.id


# ---------------------------------------------------------------------------
# assign/unassign sets FK
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAssignSetsFK:

    def test_assign_sets_user_fk(self, staff_user, agent_with_user, milestone):
        user, client = staff_user
        agent = agent_with_user
        task = TaskFactory(status="draft", milestone=milestone)

        response = client.post(
            f"/v1/tasks/{task.id}/assign/",
            {"assigned_to": agent.user.username},
            format="json",
        )
        assert response.status_code == 200

        task.refresh_from_db()
        assert task.assigned_to == agent.user

    def test_unassign_clears_fk(self, staff_user, agent_with_user, milestone):
        user, client = staff_user
        agent = agent_with_user
        task = TaskFactory(status="draft", milestone=milestone, assigned_to=agent.user)

        response = client.post(f"/v1/tasks/{task.id}/unassign/")
        assert response.status_code == 200

        task.refresh_from_db()
        assert task.assigned_to is None


# ---------------------------------------------------------------------------
# created_by server-set
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreatedByServerSet:

    def test_create_sets_created_by(self, staff_user, workplan, milestone):
        user, client = staff_user
        response = client.post(
            "/v1/tasks/",
            {
                "title": "Test task",
                "project": milestone.workplan.project.id,
                "workplan": workplan.id,
                "milestone": milestone.id,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        task = Task.objects.get(id=response.data["id"])
        assert task.created_by == user

    def test_created_by_not_writable(self, staff_user, workplan, milestone):
        """Client cannot override created_by — server always sets it."""
        user, client = staff_user
        hacker = User.objects.create_user("hacker", password="pass")
        response = client.post(
            "/v1/tasks/",
            {
                "title": "Test task",
                "project": milestone.workplan.project.id,
                "workplan": workplan.id,
                "milestone": milestone.id,
                "created_by": hacker.username,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        task = Task.objects.get(id=response.data["id"])
        assert task.created_by == user  # Server-set, not hacker


# ---------------------------------------------------------------------------
# v1 serializer backward compatibility
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestV1SerializerCompat:

    def test_v1_read_claimed_by_string(self, staff_user, agent_with_user, milestone):
        user, client = staff_user
        agent = agent_with_user
        task = TaskFactory(status="doing", milestone=milestone,
                           claimed_by=agent.user)

        response = client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == 200
        assert response.data["claimed_by"] == agent.user.username

    def test_v1_read_assigned_to_string(self, staff_user, agent_with_user, milestone):
        user, client = staff_user
        agent = agent_with_user
        task = TaskFactory(status="draft", milestone=milestone,
                           assigned_to=agent.user)

        response = client.get(f"/v1/tasks/{task.id}/")
        assert response.data["assigned_to"] == agent.user.username

    def test_v1_write_assigned_to_resolves(self, staff_user, agent_with_user, milestone):
        """PATCH assigned_to with a username string resolves to User FK."""
        user, client = staff_user
        agent = agent_with_user
        task = TaskFactory(status="draft", milestone=milestone)

        response = client.patch(
            f"/v1/tasks/{task.id}/",
            {"assigned_to": agent.user.username},
            format="json",
        )
        assert response.status_code == 200

        task.refresh_from_db()
        assert task.assigned_to == agent.user

    def test_claimed_by_null_serializes_null(self, staff_user, milestone):
        user, client = staff_user
        task = TaskFactory(status="draft", milestone=milestone)

        response = client.get(f"/v1/tasks/{task.id}/")
        assert response.data["claimed_by"] is None


# ---------------------------------------------------------------------------
# N+1 query check
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestQueryOptimization:

    def test_select_related_no_n_plus_1(self, staff_user, milestone):
        """Listing tasks should not produce N+1 queries for identity fields."""
        user, client = staff_user
        agent = AgentFactory(name="query-agent")

        # Create 5 tasks with various identity fields set
        for i in range(5):
            TaskFactory(
                status="draft",
                milestone=milestone,
                assigned_to=agent.user,
                created_by=user,
            )

        with CaptureQueriesContext(connection) as ctx:
            response = client.get("/v1/tasks/")
            assert response.status_code == 200

        # Should be a bounded number of queries (not scaling with task count)
        # Typically: 1 auth + 1 count + 1 task list + prefetches
        assert len(ctx) < 10, f"Too many queries ({len(ctx)}): possible N+1"


# ---------------------------------------------------------------------------
# Data migration
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDataMigrationSemantics:
    """Test the FK field semantics that the data migration depends on."""

    def test_task_with_user_fk(self, milestone):
        user = User.objects.create_user("test-owner")
        task = TaskFactory(milestone=milestone, created_by=user, claimed_by=user)
        task.refresh_from_db()
        assert task.created_by == user
        assert task.claimed_by == user

    def test_task_null_identity_fields(self, milestone):
        task = TaskFactory(milestone=milestone)
        task.refresh_from_db()
        assert task.claimed_by is None
        assert task.assigned_to is None
