import os

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import include, path, re_path

from core.views import BulkImportView, HealthCheckView


def custom_404(request, exception=None):
    return JsonResponse(
        {'detail': 'Not found.'},
        status=404,
    )


def serve_spa(request, path=''):
    """Serve the SPA index.html for all non-API, non-admin routes.

    This enables client-side routing — React Router handles the actual
    route matching in the browser. Django just needs to return index.html
    for any path the SPA might handle.

    In production (Docker), the SPA is copied to /app/static/spa/ by the
    Dockerfile multi-stage build and served from there.
    """
    # Primary location: Docker build copies SPA here
    candidates = [
        '/app/static/spa/index.html',
    ]
    # Also check STATIC_ROOT/spa/index.html in case collectstatic was used
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        candidates.append(os.path.join(static_root, 'spa', 'index.html'))

    for spa_index in candidates:
        if os.path.exists(spa_index):
            with open(spa_index, 'rb') as f:
                return HttpResponse(f.read(), content_type='text/html')

    # Fallback when the SPA hasn't been built (dev mode without Vite)
    return JsonResponse(
        {'detail': 'Not found.'},
        status=404,
    )


urlpatterns = [
    path('admin/', admin.site.urls),
    path('v1/health', HealthCheckView.as_view(), name='health-check'),
    path('v1/bulk/import', BulkImportView.as_view(), name='bulk-import'),
    path('v1/', include('workplans.urls')),
    path('v1/', include('agents.urls')),
    path('v1/', include('tasks.urls')),
    path('v1/', include('events.urls')),
    path('v1/', include('links.urls')),
    path('v1/', include('reviews.urls')),
]

handler404 = custom_404

# SPA catch-all — must come LAST. Serves index.html for any route that isn't
# /v1/* (API) or /admin/* (Django admin). This allows React Router to handle
# client-side navigation when the user refreshes or deep-links.
urlpatterns += [
    re_path(r'^(?!v1/|admin/).*$', serve_spa),
]
