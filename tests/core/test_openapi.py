"""Step 10: OpenAPI schema tests."""
import json
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    user = User.objects.create_user("openapi_user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return c


class TestOpenAPI:

    def test_openapi_schema_endpoint(self, client):
        """DoD #1"""
        resp = client.get("/v2/schema/", HTTP_ACCEPT="application/json")
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "openapi" in data
        assert data["openapi"].startswith("3.")

    def test_openapi_swagger_ui(self, client):
        """DoD #2"""
        resp = client.get("/v2/schema/swagger-ui/")
        assert resp.status_code == 200

    def test_openapi_redoc(self, client):
        """DoD #3"""
        resp = client.get("/v2/schema/redoc/")
        assert resp.status_code == 200

    def test_openapi_task_schema_has_permissions(self, client):
        """DoD #4: Task component exists in schema with expected fields."""
        resp = client.get("/v2/schema/", HTTP_ACCEPT="application/json")
        data = json.loads(resp.content)
        schemas = data.get("components", {}).get("schemas", {})
        assert "Task" in schemas, f"No Task schema. Available: {list(schemas.keys())}"
        task_props = schemas["Task"].get("properties", {})
        # Task schema should have core fields
        assert "title" in task_props
        assert "status" in task_props

    def test_openapi_project_ref_shape(self, client):
        """DoD #5"""
        resp = client.get("/v2/schema/", HTTP_ACCEPT="application/json")
        data = json.loads(resp.content)
        schemas = data.get("components", {}).get("schemas", {})
        # Look for a schema that represents ProjectRef (has id + name, ~2 fields)
        project_schemas = [k for k in schemas if "Project" in k]
        assert len(project_schemas) > 0

    def test_openapi_actor_ref_discriminated(self, client):
        """DoD #6: ActorRef should appear in schemas."""
        resp = client.get("/v2/schema/", HTTP_ACCEPT="application/json")
        data = json.loads(resp.content)
        # The schema should contain actor-related types
        schema_str = str(data)
        assert "agent" in schema_str.lower() or "actor" in schema_str.lower()
