import os
from unittest.mock import patch

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """GET /v1/health returns 200 with db ok and redis ok or skipped."""
        response = client.get("/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["checks"]["db"] == "ok"
        assert data["checks"]["redis"] in ("ok", "skipped")

    def test_health_returns_503_when_db_down(self, client):
        """When DB connection fails, health returns 503."""
        with patch(
            "django.db.connection.ensure_connection",
            side_effect=Exception("DB connection refused"),
        ):
            response = client.get("/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data["checks"]["db"]

    def test_health_returns_503_when_redis_down(self, client):
        """When Redis connection fails, health returns 503."""
        with patch.dict(
            os.environ, {"CELERY_BROKER_URL": "redis://localhost:6379/0"}
        ):
            with patch(
                "redis.Redis.from_url",
                side_effect=Exception("Redis connection refused"),
            ):
                response = client.get("/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data["checks"]["redis"]

    def test_health_response_format(self, client):
        """Verify JSON structure matches expected format."""
        response = client.get("/v1/health")
        assert response.status_code in (200, 503)
        data = response.json()
        # Top-level keys
        assert "status" in data
        assert "checks" in data
        # Status value
        assert data["status"] in ("healthy", "unhealthy")
        # Checks sub-keys
        assert "db" in data["checks"]
        assert "redis" in data["checks"]
        # Content type
        assert response["Content-Type"] == "application/json"
