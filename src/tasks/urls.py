from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import NoteViewSet, MilestoneTasksView, ProjectTasksView, TaskViewSet

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")

urlpatterns = router.urls + [
    path(
        "projects/<str:project_id>/tasks/",
        ProjectTasksView.as_view(),
        name="project-tasks",
    ),
    path(
        "milestones/<str:milestone_id>/tasks/",
        MilestoneTasksView.as_view(),
        name="milestone-tasks",
    ),
    path(
        "tasks/<str:task_id>/notes/",
        NoteViewSet.as_view({"get": "list", "post": "create"}),
        name="task-notes",
    ),
]
