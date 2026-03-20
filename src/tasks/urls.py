from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PhaseTasksView, TaskViewSet

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")

urlpatterns = router.urls + [
    path(
        "phases/<str:phase_id>/tasks/",
        PhaseTasksView.as_view(),
        name="phase-tasks",
    ),
]
