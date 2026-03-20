from rest_framework.routers import DefaultRouter

from .views import WorkplanViewSet

router = DefaultRouter()
router.register(r"workplans", WorkplanViewSet, basename="workplan")

urlpatterns = router.urls
