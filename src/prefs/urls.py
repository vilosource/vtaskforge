from django.urls import path

from .views import RecentAccessView

urlpatterns = [
    path("recent/", RecentAccessView.as_view(), name="recent-access"),
]
