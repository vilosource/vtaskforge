from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import PhaseViewSet, WorkplanPhasesView, WorkplanViewSet

router = DefaultRouter()
router.register(r"workplans", WorkplanViewSet, basename="workplan")
router.register(r"phases", PhaseViewSet, basename="phase")

urlpatterns = router.urls + [
    path(
        "workplans/<str:workplan_id>/phases/",
        WorkplanPhasesView.as_view(),
        name="workplan-phases",
    ),
]
