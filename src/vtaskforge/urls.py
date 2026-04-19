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
from prefs.views import (
    ChannelMappingDetailView,
    ChannelMappingView,
    ExternalIdentityDetailView,
    ExternalIdentityView,
    LockDetailView,
    LockView,
    ServiceAccountView,
    ProjectSessionsView,
    SessionCreateView,
    SessionTokenView,
    TokenValidationView,
    UserDetailView,
    UserListView,
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


from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/console-login/', console_login_redirect, name='console-login'),
    # OpenAPI schema and docs (v2 only)
    path('v2/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('v2/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('v2/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Build versioned URL patterns for both v1 and v2
# URLPrefixVersioning extracts version from the path prefix (no captured kwarg needed)
for _v in ('v1', 'v2'):
    urlpatterns += [
        path(f'{_v}/auth/login', api_login, name=f'{_v}-api-login'),
        path(f'{_v}/auth/logout', api_logout, name=f'{_v}-api-logout'),
        path(f'{_v}/auth/token/', SessionTokenView.as_view(), name=f'{_v}-session-token'),
        path(f'{_v}/auth/validate/', TokenValidationView.as_view(), name=f'{_v}-token-validate'),
        path(f'{_v}/auth/code/', ConsoleCodeGenerateView.as_view(), name=f'{_v}-console-code-generate'),
        path(f'{_v}/auth/exchange/', ConsoleCodeExchangeView.as_view(), name=f'{_v}-console-code-exchange'),
        path(f'{_v}/health', HealthCheckView.as_view(), name=f'{_v}-health-check'),
        path(f'{_v}/bulk/import', BulkImportView.as_view(), name=f'{_v}-bulk-import'),
        path(f'{_v}/', include('projects.urls')),
        path(f'{_v}/', include('workplans.urls')),
        path(f'{_v}/', include('agents.urls')),
        path(f'{_v}/', include('tasks.urls')),
        path(f'{_v}/', include('events.urls')),
        path(f'{_v}/', include('links.urls')),
        path(f'{_v}/', include('reviews.urls')),
        path(f'{_v}/external-identities/', ExternalIdentityView.as_view(), name=f'{_v}-external-identities'),
        path(f'{_v}/external-identities/<int:pk>/', ExternalIdentityDetailView.as_view(), name=f'{_v}-external-identity-detail'),
        path(f'{_v}/locks/', LockView.as_view(), name=f'{_v}-locks'),
        path(f'{_v}/locks/<int:pk>/', LockDetailView.as_view(), name=f'{_v}-lock-detail'),
        path(f'{_v}/channel-mappings/', ChannelMappingView.as_view(), name=f'{_v}-channel-mappings'),
        path(f'{_v}/channel-mappings/<int:pk>/', ChannelMappingDetailView.as_view(), name=f'{_v}-channel-mapping-detail'),
        path(f'{_v}/users/', UserListView.as_view(), name=f'{_v}-user-list'),
        path(f'{_v}/users/<int:pk>/', UserDetailView.as_view(), name=f'{_v}-user-detail'),
        path(f'{_v}/sessions/', SessionCreateView.as_view(), name=f'{_v}-session-create'),
        path(f'{_v}/sessions/project/<str:project_id>/', ProjectSessionsView.as_view(), name=f'{_v}-sessions-project'),
        path(f'{_v}/service-accounts/', ServiceAccountView.as_view(), name=f'{_v}-service-accounts'),
        path(f'{_v}/profile/', include('prefs.urls')),
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
