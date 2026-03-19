# Import celery app so it's loaded on Django startup
from vtaskforge.celery import app as celery_app

__all__ = ('celery_app',)
