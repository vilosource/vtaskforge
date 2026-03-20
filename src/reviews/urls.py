from django.urls import path

from .views import ReviewViewSet

urlpatterns = [
    path(
        "tasks/<str:task_id>/reviews/",
        ReviewViewSet.as_view({"get": "list", "post": "create"}),
        name="task-reviews",
    ),
]
