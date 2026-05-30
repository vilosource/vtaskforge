"""API tests for ProjectVariableViewSet (C.2 Slice 3).

Nested under /projects/{project_id}/variables/. Detail routes address variables
by their surrogate PK (a name is not unique without the role).
"""
import pytest
from django.contrib.auth.models import User
from rest_framework import status

from prefs.models import ProjectMembership
from tests.factories import ProjectFactory, ProjectVariableFactory
from variables.models import ProjectVariable


def _results(resp):
    return resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data


@pytest.fixture
def project(db, api_client):
    """A project the api_client user owns (membership granted)."""
    p = ProjectFactory()
    user = User.objects.get(username="testuser")
    ProjectMembership.objects.create(user=user, project_id=p.id, role="owner")
    return p


@pytest.mark.django_db
class TestCreate:
    def test_create_201_with_defaults(self, api_client, project):
        r = api_client.post(
            f"/v1/projects/{project.id}/variables/",
            {"name": "GH_TOKEN", "role": "executor"}, format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["name"] == "GH_TOKEN"
        assert r.data["role"] == "executor"
        assert r.data["scope"] == "project"
        assert r.data["required"] is True

    def test_create_via_slug(self, api_client, project):
        r = api_client.post(
            f"/v1/projects/{project.slug}/variables/",
            {"name": "X", "role": "judge"}, format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    def test_duplicate_rejected(self, api_client, project):
        ProjectVariableFactory(project=project, name="GH_TOKEN", role="executor")
        r = api_client.post(
            f"/v1/projects/{project.id}/variables/",
            {"name": "GH_TOKEN", "role": "executor"}, format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_same_name_other_role_ok(self, api_client, project):
        ProjectVariableFactory(project=project, name="GH_TOKEN", role="executor")
        r = api_client.post(
            f"/v1/projects/{project.id}/variables/",
            {"name": "GH_TOKEN", "role": "judge"}, format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    def test_near_match_warns_without_force(self, api_client, project):
        ProjectVariableFactory(project=project, name="GH_TOKEN", role="executor")
        r = api_client.post(
            f"/v1/projects/{project.id}/variables/",
            {"name": "GH_TOKE", "role": "executor"}, format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "GH_TOKEN" in str(r.data)

    def test_near_match_force_creates(self, api_client, project):
        ProjectVariableFactory(project=project, name="GH_TOKEN", role="executor")
        r = api_client.post(
            f"/v1/projects/{project.id}/variables/?force=true",
            {"name": "GH_TOKE", "role": "executor"}, format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED

    def test_invalid_role_rejected(self, api_client, project):
        r = api_client.post(
            f"/v1/projects/{project.id}/variables/",
            {"name": "X", "role": "bogus"}, format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestList:
    def test_list_scoped_to_project(self, api_client, project):
        ProjectVariableFactory(project=project, name="A", role="executor")
        other = ProjectFactory()
        ProjectVariableFactory(project=other, name="B", role="executor")
        r = api_client.get(f"/v1/projects/{project.id}/variables/")
        assert r.status_code == status.HTTP_200_OK
        names = [v["name"] for v in _results(r)]
        assert "A" in names and "B" not in names

    def test_filter_by_role(self, api_client, project):
        ProjectVariableFactory(project=project, name="A", role="executor")
        ProjectVariableFactory(project=project, name="B", role="judge")
        r = api_client.get(f"/v1/projects/{project.id}/variables/?role=judge")
        names = [v["name"] for v in _results(r)]
        assert names == ["B"]


@pytest.mark.django_db
class TestUpdateDelete:
    def test_patch_mutable_fields(self, api_client, project):
        v = ProjectVariableFactory(project=project, name="A", role="executor")
        r = api_client.patch(
            f"/v1/projects/{project.id}/variables/{v.id}/",
            {"description": "new desc", "required": False, "scope": "shared"}, format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.data["description"] == "new desc"
        assert r.data["required"] is False
        assert r.data["scope"] == "shared"

    def test_patch_name_rejected(self, api_client, project):
        v = ProjectVariableFactory(project=project, name="A", role="executor")
        r = api_client.patch(
            f"/v1/projects/{project.id}/variables/{v.id}/",
            {"name": "B"}, format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_role_rejected(self, api_client, project):
        v = ProjectVariableFactory(project=project, name="A", role="executor")
        r = api_client.patch(
            f"/v1/projects/{project.id}/variables/{v.id}/",
            {"role": "judge"}, format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete(self, api_client, project):
        v = ProjectVariableFactory(project=project, name="A", role="executor")
        r = api_client.delete(f"/v1/projects/{project.id}/variables/{v.id}/")
        assert r.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)
        assert not ProjectVariable.objects.filter(id=v.id).exists()


@pytest.mark.django_db
class TestAuth:
    def test_unauthenticated_denied(self, unauthenticated_client, project):
        r = unauthenticated_client.get(f"/v1/projects/{project.id}/variables/")
        assert r.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_see(self, api_client):
        other = ProjectFactory()
        ProjectVariableFactory(project=other, name="A", role="executor")
        r = api_client.get(f"/v1/projects/{other.id}/variables/")
        assert r.status_code == status.HTTP_403_FORBIDDEN or (
            r.status_code == status.HTTP_200_OK and len(_results(r)) == 0
        )
