import os

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import include, path, re_path

from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from core.views import (
    BulkImportView,
    ConsoleCodeExchangeView,
    ConsoleCodeGenerateView,
    HealthCheckView,
    console_login_redirect,
)


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


import json as json_module


@ensure_csrf_cookie
def api_login(request):
    """POST /v1/auth/login — session login for browser users."""
    if request.method == 'GET':
        # GET returns CSRF cookie + current auth status
        if request.user.is_authenticated:
            return JsonResponse({'authenticated': True, 'username': request.user.username})
        return JsonResponse({'authenticated': False})

    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        data = json_module.loads(request.body)
    except (json_module.JSONDecodeError, ValueError):
        return JsonResponse({'detail': 'Invalid JSON.'}, status=400)

    username = data.get('username', '')
    password = data.get('password', '')
    if not username or not password:
        return JsonResponse({'detail': 'Username and password required.'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({'detail': 'Invalid credentials.'}, status=401)

    login(request, user)
    return JsonResponse({'authenticated': True, 'username': user.username})


def api_logout(request):
    """POST /v1/auth/logout — session logout."""
    logout(request)
    return JsonResponse({'authenticated': False})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('v1/auth/login', api_login, name='api-login'),
    path('v1/auth/logout', api_logout, name='api-logout'),
    path('v1/auth/code/', ConsoleCodeGenerateView.as_view(), name='console-code-generate'),
    path('v1/auth/exchange/', ConsoleCodeExchangeView.as_view(), name='console-code-exchange'),
    path('auth/console-login/', console_login_redirect, name='console-login'),
    path('v1/health', HealthCheckView.as_view(), name='health-check'),
    path('v1/bulk/import', BulkImportView.as_view(), name='bulk-import'),
    path('v1/', include('projects.urls')),
    path('v1/', include('workplans.urls')),
    path('v1/', include('agents.urls')),
    path('v1/', include('tasks.urls')),
    path('v1/', include('events.urls')),
    path('v1/', include('links.urls')),
    path('v1/', include('reviews.urls')),
]

handler404 = custom_404

# SPA static assets — serve JS/CSS/images from the built SPA directory
def serve_spa_asset(request, asset_path):
    """Serve SPA static assets (JS, CSS, images) with correct MIME types."""
    import mimetypes
    candidates = [
        f'/app/static/spa/assets/{asset_path}',
    ]
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        candidates.append(os.path.join(static_root, 'spa', 'assets', asset_path))

    for filepath in candidates:
        if os.path.exists(filepath):
            content_type, _ = mimetypes.guess_type(filepath)
            return FileResponse(open(filepath, 'rb'), content_type=content_type or 'application/octet-stream')

    return JsonResponse({'detail': 'Not found.'}, status=404)


# SPA catch-all — must come LAST. Serves index.html for any route that isn't
# /v1/* (API), /admin/* (Django admin), or /assets/* (SPA static files).
urlpatterns += [
    path('assets/<path:asset_path>', serve_spa_asset),
    re_path(r'^(?!v1/|admin/|assets/).*$', serve_spa),
]
