"""Step 9: v2 Prefs serializer tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from prefs.models import AgentLock, ChannelProjectMapping, ProjectMembership

    user = User.objects.create_user("prefsv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="PrefsProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    lock = AgentLock.objects.create(user=user, project_id=project.id, role="architect")
    mapping = ChannelProjectMapping.objects.create(
        provider="slack", channel_id="C123", channel_name="#dev", project_id=project.id,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user, project, lock, mapping


class TestPrefsV2:

    def test_v2_lock_user_is_actor_ref(self, setup):
        """DoD #1"""
        client, _, _, _, _ = setup
        resp = client.get("/v2/locks/")
        assert resp.status_code == 200
        lck = resp.data["results"][0]
        assert isinstance(lck["user"], dict)
        assert lck["user"]["type"] == "user"

    def test_v2_lock_project_is_ref(self, setup):
        """DoD #2"""
        client, _, project, _, _ = setup
        resp = client.get("/v2/locks/")
        lck = resp.data["results"][0]
        assert isinstance(lck["project"], dict)
        assert lck["project"]["id"] == project.id

    def test_v1_lock_unchanged(self, setup):
        """DoD #3"""
        client, user, _, _, _ = setup
        resp = client.get("/v1/locks/")
        lck = resp.data["results"][0]
        assert isinstance(lck["user"], str)
        assert lck["user"] == user.username

    def test_v2_channel_mapping_project_is_ref(self, setup):
        """DoD #4"""
        client, _, project, _, _ = setup
        resp = client.get("/v2/channel-mappings/")
        m = resp.data["results"][0]
        assert isinstance(m["project"], dict)
        assert m["project"]["id"] == project.id

    def test_v1_channel_mapping_unchanged(self, setup):
        """DoD #5"""
        client, _, project, _, _ = setup
        resp = client.get("/v1/channel-mappings/")
        m = resp.data["results"][0]
        assert m["project_id"] == project.id

    def test_v2_token_validate_projects_have_ref(self, setup):
        """DoD #6"""
        client, _, _, _, _ = setup
        resp = client.get("/v2/auth/validate/")
        assert resp.status_code == 200
        proj = resp.data["projects"][0]
        assert "project" in proj
        assert isinstance(proj["project"], dict)

    def test_v1_token_validate_unchanged(self, setup):
        """DoD #7"""
        client, _, _, _, _ = setup
        resp = client.get("/v1/auth/validate/")
        proj = resp.data["projects"][0]
        assert "project_id" in proj

    def test_v2_user_detail_memberships_have_ref(self, setup):
        """DoD #8"""
        client, user, _, _, _ = setup
        resp = client.get(f"/v2/users/{user.pk}/")
        assert resp.status_code == 200
        m = resp.data["memberships"][0]
        assert isinstance(m["user"], dict)
        assert isinstance(m["project"], dict)

    def test_v2_members_list_has_refs(self, setup):
        """DoD #9"""
        client, _, project, _, _ = setup
        resp = client.get(f"/v2/projects/{project.id}/members/")
        assert resp.status_code == 200
        m = resp.data["results"][0]
        assert isinstance(m["user"], dict)
        assert isinstance(m["project"], dict)

    def test_v1_user_detail_unchanged(self, setup):
        """DoD #10"""
        client, user, _, _, _ = setup
        resp = client.get(f"/v1/users/{user.pk}/")
        m = resp.data["memberships"][0]
        assert "user_id" in m
        assert "username" in m
        assert "project_id" in m
