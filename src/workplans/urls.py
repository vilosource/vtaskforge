from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MilestoneViewSet, WorkplanMilestonesView, WorkplanViewSet

router = DefaultRouter()
router.register(r"workplans", WorkplanViewSet, basename="workplan")
router.register(r"milestones", MilestoneViewSet, basename="milestone")

urlpatterns = router.urls + [
    path(
        "workplans/<str:workplan_id>/milestones/",
        WorkplanMilestonesView.as_view(),
        name="workplan-milestones",
    ),
]
