from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ProjectBacklogView,
    ProjectMemberDetailView,
    ProjectMemberView,
    ProjectViewSet,
    ProjectWorkplansView,
)

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
    path(
        "projects/<str:project_id>/members/",
        ProjectMemberView.as_view(),
        name="project-members",
    ),
    path(
        "projects/<str:project_id>/members/<int:pk>/",
        ProjectMemberDetailView.as_view(),
        name="project-member-detail",
    ),
]