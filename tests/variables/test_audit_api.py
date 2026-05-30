"""API tests for the VariableAudit write endpoint (C.3 Slice 4 receiver).

The vafi controller POSTs one audit row per Vault read. The endpoint is
create + (scoped) list; it never accepts/stores the secret value.
"""
import pytest
from django.contrib.auth.models import User
from rest_framework import status

from prefs.models import ProjectMembership
from tests.factories import ProjectFactory, TaskFactory
from variables.models import VariableAudit


@pytest.fixture
def member_project(db, api_client):
    p = ProjectFactory()
    ProjectMembership.objects.create(
        user=User.objects.get(username="testuser"), project_id=p.id, role="owner"
    )
    return p


@pytest.fixture
def outsider_client(db):
    from rest_framework.authtoken.models import Token
    from rest_framework.test import APIClient
    user = User.objects.create_user(username="outsider", password="x", is_staff=False)
    token = Token.objects.create(user=user)
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return c


def _payload(project, task, **over):
    p = {
        "task": task.id,
        "project": project.id,
        "variable_name": "GH_TOKEN",
        "variable_scope": "project",
        "vault_path": "secret/apps/vtaskforge/dev/projects/abad/executor/GH_TOKEN",
        "vault_version": 3,
        "result": "success",
        "size_bytes": 47,
        "duration_ms": 12,
        "controller_id": "controller-0",
        "timestamp": "2026-05-30T10:00:00Z",
    }
    p.update(over)
    return p


@pytest.mark.django_db
class TestVariableAuditCreate:
    def test_create_201(self, api_client, member_project):
        task = TaskFactory(project=member_project)
        r = api_client.post("/v1/variable-audits/", _payload(member_project, task), format="json")
        assert r.status_code == status.HTTP_201_CREATED
        assert "audit_id" in r.data
        assert VariableAudit.objects.filter(variable_name="GH_TOKEN").exists()

    def test_create_each_result(self, api_client, member_project):
        task = TaskFactory(project=member_project)
        for res in ["success", "not_found", "empty", "unreachable", "permission_denied"]:
            r = api_client.post(
                "/v1/variable-audits/", _payload(member_project, task, result=res), format="json"
            )
            assert r.status_code == status.HTTP_201_CREATED

    def test_failure_result_allows_null_version_and_size(self, api_client, member_project):
        task = TaskFactory(project=member_project)
        r = api_client.post(
            "/v1/variable-audits/",
            _payload(member_project, task, result="not_found", vault_version=None, size_bytes=None),
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    def test_no_value_field_in_surface(self, api_client, member_project):
        task = TaskFactory(project=member_project)
        # a value-bearing field must be silently ignored, never stored
        r = api_client.post(
            "/v1/variable-audits/", _payload(member_project, task, value="ghp_leak"), format="json"
        )
        assert r.status_code == status.HTTP_201_CREATED
        for forbidden in ("value", "value_hash", "secret", "data"):
            assert forbidden not in r.data

    def test_unauthenticated_denied(self, unauthenticated_client, member_project):
        task = TaskFactory(project=member_project)
        r = unauthenticated_client.post(
            "/v1/variable-audits/", _payload(member_project, task), format="json"
        )
        assert r.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.django_db
class TestVariableAuditList:
    def _row(self, project, name, task=None):
        return VariableAudit.objects.create(
            project=project, task=task, variable_name=name, variable_scope="project",
            vault_path="p", result="success", duration_ms=1, controller_id="c",
            timestamp="2026-05-30T10:00:00Z",
        )

    def test_list_returns_200(self, api_client, member_project):
        self._row(member_project, "A", TaskFactory(project=member_project))
        r = api_client.get("/v1/variable-audits/")
        assert r.status_code == status.HTTP_200_OK
        names = [a["variable_name"] for a in (r.data.get("results", r.data))]
        assert "A" in names

    def test_list_scoped_for_non_member(self, outsider_client, member_project):
        self._row(member_project, "A")
        r = outsider_client.get("/v1/variable-audits/")
        assert r.status_code == status.HTTP_200_OK
        names = [a["variable_name"] for a in (r.data.get("results", r.data))]
        assert "A" not in names  # outsider sees none of member_project's audits
