from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from tests.factories import AgentFactory, TaskFactory, WorkplanFactory, MilestoneFactory


@pytest.fixture(scope="session")
def django_db_setup():
    """Use default test DB settings (Django creates a test_ prefixed database)."""
    pass


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    """Run all Celery tasks synchronously in tests — no Redis needed."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client(db):
    client = APIClient()
    user = User.objects.create_user(username='testuser', password='testpass')
    token = Token.objects.create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return client


@pytest.fixture
def unauthenticated_client():
    return APIClient()


@pytest.fixture
def workplan(db):
    return WorkplanFactory()


@pytest.fixture
def milestone(db):
    return MilestoneFactory()


@pytest.fixture
def task(db):
    return TaskFactory()


@pytest.fixture
def todo_task(db):
    return TaskFactory(status="todo")


@pytest.fixture
def doing_task(db):
    return TaskFactory(
        status="doing",
        claimed_by="agent-1",
        claimed_at=timezone.now(),
        claim_expires_at=timezone.now() + timedelta(minutes=30),
    )


@pytest.fixture
def agent(db):
    return AgentFactory()
