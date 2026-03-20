from django.urls import path
from rest_framework.routers import DefaultRouter

from .stream import stream_events
from .views import TaskEventViewSet

router = DefaultRouter()
router.register(r"events", TaskEventViewSet, basename="event")

urlpatterns = [
    path("events/stream/", stream_events, name="event-stream"),
] + router.urls + [
    path(
        "tasks/<str:task_id>/events/",
        TaskEventViewSet.as_view({"get": "list"}),
        name="task-events",
    ),
]
