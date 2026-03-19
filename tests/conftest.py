import pytest


@pytest.fixture(scope="session")
def django_db_setup():
    """Use default test DB settings (Django creates a test_ prefixed database)."""
    pass


@pytest.fixture(autouse=True)
def _celery_eager(settings):
    """Run all Celery tasks synchronously in tests — no Redis needed."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
