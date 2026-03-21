from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ProjectBacklogView, ProjectViewSet, ProjectWorkplansView

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")

urlpatterns = router.urls + [
    path(
        "projects/<str:project_id>/workplans/",
        ProjectWorkplansView.as_view(),
        name="project-workplans",
    ),
    path(
        "projects/<str:project_id>/backlog/",
        ProjectBacklogView.as_view(),
        name="project-backlog",
    ),
]