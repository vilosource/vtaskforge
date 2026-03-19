from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, re_path

from core.views import HealthCheckView


def custom_404(request, exception=None):
    return JsonResponse(
        {'detail': 'Not found.'},
        status=404,
    )


def catch_all_404(request, path=''):
    return JsonResponse(
        {'detail': 'Not found.'},
        status=404,
    )


urlpatterns = [
    path('admin/', admin.site.urls),
    path('v1/health', HealthCheckView.as_view(), name='health-check'),
]

handler404 = custom_404

# Catch-all for unmatched routes — works even with DEBUG=True
urlpatterns += [
    re_path(r'^(?!admin/).*$', catch_all_404),
]
