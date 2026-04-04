"""Step 10: Idempotency middleware tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from prefs.models import ProjectMembership

    user = User.objects.create_user("idempuser", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="IdempProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, project


class TestIdempotency:

    def test_idempotency_duplicate_post(self, setup):
        """DoD #7: Same key twice returns cached response without creating duplicate."""
        client, project = setup
        key = "test-idemp-key-001"
        data = {"title": "IdempTask", "project": project.id}

        resp1 = client.post("/v2/tasks/", data, format="json", HTTP_IDEMPOTENCY_KEY=key)
        assert resp1.status_code == 201

        resp2 = client.post("/v2/tasks/", data, format="json", HTTP_IDEMPOTENCY_KEY=key)
        assert resp2.status_code == 201
        # Same response — same task ID
        assert resp2.json()["id"] == resp1.json()["id"]

    def test_idempotency_different_key(self, setup):
        """DoD #8: Different key creates a new resource."""
        client, project = setup
        data = {"title": "IdempTask2", "project": project.id}

        resp1 = client.post("/v2/tasks/", data, format="json", HTTP_IDEMPOTENCY_KEY="key-a")
        resp2 = client.post("/v2/tasks/", data, format="json", HTTP_IDEMPOTENCY_KEY="key-b")
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] != resp2.json()["id"]

    def test_idempotency_no_header(self, setup):
        """DoD #9: POST without key processes normally."""
        client, project = setup
        resp = client.post("/v2/tasks/", {"title": "NoKeyTask", "project": project.id}, format="json")
        assert resp.status_code == 201

    def test_idempotency_v1_ignored(self, setup):
        """DoD #10: POST to /v1/ with key is ignored."""
        client, project = setup
        resp1 = client.post("/v1/tasks/", {"title": "V1Task", "project": project.id}, format="json", HTTP_IDEMPOTENCY_KEY="v1-key")
        resp2 = client.post("/v1/tasks/", {"title": "V1Task2", "project": project.id}, format="json", HTTP_IDEMPOTENCY_KEY="v1-key")
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        # Different tasks created (not cached)
        assert resp1.json()["id"] != resp2.json()["id"]

    def test_idempotency_get_ignored(self, setup):
        """DoD #11: GET with key is ignored."""
        client, project = setup
        resp = client.get("/v2/tasks/", HTTP_IDEMPOTENCY_KEY="get-key")
        assert resp.status_code == 200
