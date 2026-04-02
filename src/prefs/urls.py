from django.urls import path

from .views import RecentAccessView, SessionHistoryView

urlpatterns = [
    path("recent/", RecentAccessView.as_view(), name="recent-access"),
    path("sessions/", SessionHistoryView.as_view(), name="session-history"),
]
