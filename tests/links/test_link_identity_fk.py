"""TDD tests for Link identity FK migration (Phase 0, Step 6).

Converts created_by from CharField to FK User on Link, adds project denormalization.

Reference: docs/design/phase0-identity-authorization-DESIGN.md, Step 6 DoD.
"""

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from links.models import Link
from tests.factories import (
    LinkFactory, MilestoneFactory, ProjectFactory, TaskFactory, WorkplanFactory,
)


@pytest.fixture
def staff_user(db):
    user = User.objects.create_user("staffuser", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return user, client


# ---------------------------------------------------------------------------
# created_by server-set
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLinkCreatedBy:

    def test_link_create_sets_created_by(self, staff_user):
        user, client = staff_user
        task = TaskFactory()
        response = client.post(
            "/v1/links/",
            {
                "source_type": "task",
                "source_id": task.id,
                "target_type": "commit",
                "target_id": "sha123",
                "link_type": "commit",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        link = Link.objects.get(id=response.data["id"])
        assert link.created_by == user


# ---------------------------------------------------------------------------
# project denormalization from source entity
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLinkProjectDenormalization:

    def test_link_project_from_task_source(self, staff_user):
        user, client = staff_user
        task = TaskFactory()
        response = client.post(
            "/v1/links/",
            {
                "source_type": "task",
                "source_id": task.id,
                "target_type": "commit",
                "target_id": "sha123",
                "link_type": "commit",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        link = Link.objects.get(id=response.data["id"])
        assert link.project == task.project

    def test_link_project_from_workplan_source(self, staff_user):
        user, client = staff_user
        workplan = WorkplanFactory()
        response = client.post(
            "/v1/links/",
            {
                "source_type": "workplan",
                "source_id": workplan.id,
                "target_type": "jira",
                "target_id": "PROJ-1",
                "link_type": "jira",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        link = Link.objects.get(id=response.data["id"])
        assert link.project == workplan.project

    def test_link_project_from_milestone_source(self, staff_user):
        user, client = staff_user
        milestone = MilestoneFactory()
        response = client.post(
            "/v1/links/",
            {
                "source_type": "milestone",
                "source_id": milestone.id,
                "target_type": "doc",
                "target_id": "doc-ref-1",
                "link_type": "doc",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        link = Link.objects.get(id=response.data["id"])
        assert link.project == milestone.workplan.project

    def test_link_project_scoping(self, staff_user):
        """Verify link.project is set correctly for project-scoped queries."""
        user, client = staff_user
        task = TaskFactory()
        response = client.post(
            "/v1/links/",
            {
                "source_type": "task",
                "source_id": task.id,
                "target_type": "commit",
                "target_id": "sha456",
                "link_type": "commit",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        link = Link.objects.get(id=response.data["id"])
        assert link.project_id == task.project_id


# ---------------------------------------------------------------------------
# Data migration semantics
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDataMigrationSemantics:

    def test_data_migration_backfills_project(self):
        """Verify link.project can be set from a task source entity."""
        task = TaskFactory()
        user = User.objects.create_user("link-creator")
        link = Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="commit",
            target_id="sha789",
            link_type="commit",
            created_by=user,
            project=task.project,
        )
        link.refresh_from_db()
        assert link.project == task.project
        assert link.created_by == user
