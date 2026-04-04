"""Step 5: v2 Workplan and Milestone serializer tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from workplans.models import Workplan, Milestone
    from prefs.models import ProjectMembership

    user = User.objects.create_user("wpv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="WPV2Proj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    workplan = Workplan.objects.create(
        name="WPV2", project=project, owner=user, created_by=user,
    )
    milestone = Milestone.objects.create(
        name="MSV2", workplan=workplan, status="active", created_by=user,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user, project, workplan, milestone


class TestWorkplanV2:

    def test_v2_workplan_project_is_ref(self, setup):
        """DoD #7"""
        client, user, project, workplan, _ = setup
        resp = client.get(f"/v2/workplans/{workplan.id}/")
        assert resp.status_code == 200
        proj = resp.data["project"]
        assert isinstance(proj, dict)
        assert proj["id"] == project.id
        assert proj["name"] == "WPV2Proj"

    def test_v2_workplan_owner_is_actor_ref(self, setup):
        """DoD #8"""
        client, _, _, workplan, _ = setup
        resp = client.get(f"/v2/workplans/{workplan.id}/")
        assert isinstance(resp.data["owner"], dict)
        assert resp.data["owner"]["type"] == "user"

    def test_v2_workplan_has_permissions(self, setup):
        """DoD #9"""
        client, _, _, workplan, _ = setup
        resp = client.get(f"/v2/workplans/{workplan.id}/")
        perms = resp.data["permissions"]
        assert "can_edit" in perms
        assert "can_delete" in perms
        assert "can_archive" in perms
        assert "can_complete" in perms

    def test_v1_workplan_unchanged(self, setup):
        """DoD #10"""
        client, _, project, workplan, _ = setup
        resp = client.get(f"/v1/workplans/{workplan.id}/")
        assert resp.status_code == 200
        # v1: project is a bare ID string
        assert resp.data["project"] == project.id
        assert "permissions" not in resp.data

    def test_v2_workplan_create_accepts_bare_id(self, setup):
        """DoD #11"""
        client, _, project, _, _ = setup
        resp = client.post(
            "/v2/workplans/",
            {"name": "NewWP", "project": project.id},
            format="json",
        )
        assert resp.status_code == 201
        assert isinstance(resp.data["project"], dict)


class TestMilestoneV2:

    def test_v2_milestone_workplan_is_ref(self, setup):
        """DoD #12"""
        client, _, _, workplan, milestone = setup
        resp = client.get(f"/v2/milestones/{milestone.id}/")
        assert resp.status_code == 200
        wp = resp.data["workplan"]
        assert isinstance(wp, dict)
        assert wp["id"] == workplan.id
        assert wp["name"] == "WPV2"

    def test_v2_milestone_created_by_is_actor_ref(self, setup):
        """DoD #13"""
        client, _, _, _, milestone = setup
        resp = client.get(f"/v2/milestones/{milestone.id}/")
        assert isinstance(resp.data["created_by"], dict)

    def test_v2_milestone_has_permissions(self, setup):
        """DoD #14"""
        client, _, _, _, milestone = setup
        resp = client.get(f"/v2/milestones/{milestone.id}/")
        perms = resp.data["permissions"]
        assert "can_edit" in perms

    def test_v2_milestone_create_accepts_bare_id(self, setup):
        """DoD #15"""
        client, _, _, workplan, _ = setup
        resp = client.post(
            "/v2/milestones/",
            {"name": "NewMS", "workplan": workplan.id},
            format="json",
        )
        assert resp.status_code == 201
        assert isinstance(resp.data["workplan"], dict)
