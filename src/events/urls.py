from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import TaskEventViewSet

router = DefaultRouter()
router.register(r"events", TaskEventViewSet, basename="event")

urlpatterns = router.urls + [
    path(
        "tasks/<str:task_id>/events/",
        TaskEventViewSet.as_view({"get": "list"}),
        name="task-events",
    ),
]
