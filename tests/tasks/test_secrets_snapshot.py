"""Tests for the controller-facing secrets-snapshot write path (C.3 #3).

POST /v1/tasks/<id>/secrets-snapshot/ persists the {variable_name: vault_version}
snapshot the vafi controller captures at spawn. Idempotent whole-value replace;
not exposed on the general Task serializer.
"""
import pytest
from rest_framework import status

from tests.factories import TaskFactory


@pytest.mark.django_db
class TestSecretsSnapshot:
    def _url(self, task):
        return f"/v1/tasks/{task.id}/secrets-snapshot/"

    def test_sets_snapshot_returns_200(self, api_client):
        task = TaskFactory(status="doing")
        snap = {"GH_TOKEN": 3, "SMOKE_TOKEN": 1}
        resp = api_client.post(self._url(task), {"snapshot": snap}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["secrets_snapshot"] == snap

    def test_persists_to_db(self, api_client):
        task = TaskFactory(status="doing")
        snap = {"GH_TOKEN": 7}
        api_client.post(self._url(task), {"snapshot": snap}, format="json")
        task.refresh_from_db()
        assert task.secrets_snapshot == snap

    def test_idempotent_replace(self, api_client):
        task = TaskFactory(status="doing", secrets_snapshot={"OLD": 1})
        api_client.post(self._url(task), {"snapshot": {"NEW": 2}}, format="json")
        task.refresh_from_db()
        assert task.secrets_snapshot == {"NEW": 2}

    def test_missing_snapshot_returns_400(self, api_client):
        task = TaskFactory(status="doing")
        resp = api_client.post(self._url(task), {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_object_snapshot_returns_400(self, api_client):
        task = TaskFactory(status="doing")
        resp = api_client.post(self._url(task), {"snapshot": "nope"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_requires_auth(self, unauthenticated_client):
        task = TaskFactory(status="doing")
        resp = unauthenticated_client.post(
            self._url(task), {"snapshot": {"X": 1}}, format="json"
        )
        assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
