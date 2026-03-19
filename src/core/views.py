import os

import redis
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


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
