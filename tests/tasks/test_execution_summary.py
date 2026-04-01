"""
Tests for the execution_summary field on Task.
"""
import pytest
from rest_framework import status

from tasks.models import Task
from tests.factories import TaskFactory


@pytest.mark.django_db
class TestExecutionSummaryModel:
    def test_task_has_execution_summary_field_null_by_default(self):
        task = TaskFactory()
        assert task.execution_summary is None

    def test_task_execution_summary_stores_json(self):
        summary = {"status": "success", "duration_s": 42, "files_changed": 3}
        task = TaskFactory(execution_summary=summary)
        task.refresh_from_db()
        assert task.execution_summary == summary


@pytest.mark.django_db
class TestExecutionSummaryAPI:
    def test_get_task_includes_execution_summary(self, api_client):
        summary = {"status": "success", "output": "All tests passed"}
        task = TaskFactory(execution_summary=summary)
        response = api_client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["execution_summary"] == summary

    def test_get_task_execution_summary_null_when_not_set(self, api_client):
        task = TaskFactory()
        response = api_client.get(f"/v1/tasks/{task.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["execution_summary"] is None

    def test_patch_task_sets_execution_summary(self, api_client):
        task = TaskFactory()
        summary = {"status": "failed", "error": "Test timeout"}
        response = api_client.patch(
            f"/v1/tasks/{task.id}/",
            data={"execution_summary": summary},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["execution_summary"] == summary
        task.refresh_from_db()
        assert task.execution_summary == summary
