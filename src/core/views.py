import os
from urllib.parse import urlencode

import redis
from django.conf import settings as django_settings
from django.db import connection
from django.http import HttpResponseRedirect
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.bulk_import import perform_bulk_import
from core.models import ConsoleAuthCode


class BulkImportView(APIView):
    """POST /v1/bulk/import — create workplan + milestones + tasks + links atomically."""

    def post(self, request):
        payload = request.data

        # Validate top-level required fields
        if "project_id" not in payload and "project" not in payload:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "project_id or project is required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if "workplan_id" not in payload and "workplan" not in payload:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "workplan or workplan_id is required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if "workplan" in payload and (not isinstance(payload["workplan"], dict) or "name" not in payload["workplan"]):
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "workplan.name is required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate milestones
        for i, milestone in enumerate(payload.get("milestones", [])):
            if "ref" not in milestone:
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": f"milestones[{i}].ref is required"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if "name" not in milestone:
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": f"milestones[{i}].name is required"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for j, task in enumerate(milestone.get("tasks", [])):
                if "ref" not in task:
                    return Response(
                        {"error": {"code": "VALIDATION_ERROR", "message": f"milestones[{i}].tasks[{j}].ref is required"}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if "title" not in task:
                    return Response(
                        {"error": {"code": "VALIDATION_ERROR", "message": f"milestones[{i}].tasks[{j}].title is required"}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # Validate backlog_tasks
        for i, task in enumerate(payload.get("backlog_tasks", [])):
            if "ref" not in task:
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": f"backlog_tasks[{i}].ref is required"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if "title" not in task:
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": f"backlog_tasks[{i}].title is required"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            ref_map = perform_bulk_import(payload)
        except ValueError as e:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build created counts
        milestones_count = len(payload.get("milestones", []))
        milestone_tasks_count = sum(len(p.get("tasks", [])) for p in payload.get("milestones", []))
        backlog_tasks_count = len(payload.get("backlog_tasks", []))
        tasks_count = milestone_tasks_count + backlog_tasks_count
        links_count = len(payload.get("links", []))

        return Response(
            {
                "ref_map": ref_map,
                "created": {
                    "workplans": 1,
                    "milestones": milestones_count,
                    "tasks": tasks_count,
                    "links": links_count,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class HealthCheckView(APIView):
    """GET /v1/health — checks DB and Redis connectivity."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        checks = {}
        healthy = True

        # Check database
        try:
            connection.ensure_connection()
            checks['db'] = 'ok'
        except Exception as e:
            checks['db'] = f'error: {e}'
            healthy = False

        # Check Redis (optional — degrades gracefully when not configured)
        try:
            broker_url = os.environ.get('CELERY_BROKER_URL', '')
            if broker_url:
                r = redis.Redis.from_url(broker_url, socket_connect_timeout=3)
                r.ping()
                checks['redis'] = 'ok'
            else:
                checks['redis'] = 'skipped'
        except Exception as e:
            checks['redis'] = f'error: {e}'
            healthy = False

        payload = {
            'status': 'healthy' if healthy else 'unhealthy',
            'checks': checks,
        }
        http_status = (
            status.HTTP_200_OK if healthy
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(payload, status=http_status)


# ---------------------------------------------------------------------------
# Console auth endpoints (vafi-console authorization code flow)
# ---------------------------------------------------------------------------


class GenerateCodeSerializer(serializers.Serializer):
    redirect_uri = serializers.URLField(required=True, max_length=500)


class ExchangeCodeSerializer(serializers.Serializer):
    code = serializers.CharField(required=True, max_length=64)


class ConsoleCodeGenerateView(APIView):
    """POST /v1/auth/code/ — generate a single-use authorization code.

    Requires authenticated session. Returns code + expiry.
    Used by vtf web when user clicks "Plan with Architect".
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GenerateCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = ConsoleAuthCode.objects.create_code(
            user=request.user,
            redirect_uri=serializer.validated_data["redirect_uri"],
        )
        return Response(
            {
                "code": code.code,
                "expires_at": code.expires_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class ConsoleCodeExchangeView(APIView):
    """POST /v1/auth/exchange/ — exchange a code for user info.

    No auth required — the code IS the auth.
    Used by vafi-console backend server-to-server.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ExchangeCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        auth_code = ConsoleAuthCode.objects.validate_code(
            serializer.validated_data["code"]
        )
        if auth_code is None:
            return Response(
                {"error": "Invalid or expired code"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            "user_id": auth_code.user.id,
            "username": auth_code.user.username,
            "is_staff": auth_code.user.is_staff,
        })


def console_login_redirect(request):
    """GET /auth/console-login/?next=URL

    If user has a Django session: generate code, redirect to console with code.
    If not: redirect to Django login (which will redirect back here after login).
    """
    next_url = request.GET.get("next", "")
    if not next_url:
        return HttpResponseRedirect("/")

    if not request.user.is_authenticated:
        login_url = getattr(django_settings, "LOGIN_URL", "/admin/login/")
        params = urlencode({"next": request.get_full_path()})
        return HttpResponseRedirect(f"{login_url}?{params}")

    # User is authenticated — generate code and redirect
    code = ConsoleAuthCode.objects.create_code(
        user=request.user,
        redirect_uri=next_url,
    )
    # Append code to the redirect URL
    separator = "&" if "?" in next_url else "?"
    redirect_url = f"{next_url}{separator}code={code.code}"
    return HttpResponseRedirect(redirect_url)
