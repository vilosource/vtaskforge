import os

import redis
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.bulk_import import perform_bulk_import


class BulkImportView(APIView):
    """POST /v1/bulk/import — create workplan + milestones + tasks + links atomically."""

    def post(self, request):
        payload = request.data

        # Validate top-level required fields
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
        for i, phase in enumerate(payload.get("milestones", [])):
            if "ref" not in phase:
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": f"milestones[{i}].ref is required"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if "name" not in phase:
                return Response(
                    {"error": {"code": "VALIDATION_ERROR", "message": f"milestones[{i}].name is required"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for j, task in enumerate(phase.get("tasks", [])):
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

        try:
            ref_map = perform_bulk_import(payload)
        except ValueError as e:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build created counts
        milestones_count = len(payload.get("milestones", []))
        tasks_count = sum(len(p.get("tasks", [])) for p in payload.get("milestones", []))
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

        # Check Redis
        try:
            broker_url = os.environ.get(
                'CELERY_BROKER_URL', 'redis://redis:6379/0'
            )
            r = redis.Redis.from_url(broker_url, socket_connect_timeout=3)
            r.ping()
            checks['redis'] = 'ok'
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
