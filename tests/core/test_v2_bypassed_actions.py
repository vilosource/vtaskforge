"""Tests for v2 endpoints that previously bypassed the VersionedSerializerMixin.

These bugs were found during E2E testing — actions that hardcoded v1 serializers
instead of using get_serializer() or version-selecting.
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from workplans.models import Workplan, Milestone
    from tasks.models import Task
    from agents.models import Agent
    from prefs.models import ProjectMembership

    user = User.objects.create_user("bypassuser", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    agent_user = User.objects.create_user("bypass-agent", password="pass")
    agent = Agent.objects.create(id="bypass-agent", name="bypass-exec", user=agent_user, pod_name="pod-bp")

    project = Project.objects.create(name="BypassProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    ProjectMembership.objects.create(user=agent_user, project_id=project.id, role="member")
    workplan = Workplan.objects.create(name="BypassWP", project=project, owner=user, created_by=user)
    milestone = Milestone.objects.create(name="BypassMS", workplan=workplan, status="active", created_by=user)
    task_todo = Task.objects.create(
        title="BypassTask", project=project, workplan=workplan,
        milestone=milestone, created_by=user, status="todo",
    )
    task_doing = Task.objects.create(
        title="DoingTask", project=project, workplan=workplan,
        milestone=milestone, created_by=user, status="doing",
        claimed_by=agent_user,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user, project, workplan, milestone, task_todo, task_doing, agent


class TestClaimableReturnsV2:
    """Bug: claimable action hardcoded TaskSerializer."""

    def test_v2_claimable_returns_refs(self, setup):
        client, _, project, _, _, _, _, _ = setup
        resp = client.get(f"/v2/tasks/claimable/?project={project.id}")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            task = results[0]
            assert isinstance(task["project"], dict), f"v2 claimable should return ProjectRef dict, got {type(task['project'])}"
            assert "name" in task["project"]

    def test_v1_claimable_returns_bare_id(self, setup):
        client, _, project, _, _, _, _, _ = setup
        resp = client.get(f"/v1/tasks/claimable/?project={project.id}")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            assert isinstance(results[0]["project"], str)


class TestProjectWorkplansReturnsV2:
    """Bug: ProjectWorkplansView hardcoded WorkplanSerializer."""

    def test_v2_project_workplans_returns_refs(self, setup):
        client, _, project, _, _, _, _, _ = setup
        resp = client.get(f"/v2/projects/{project.id}/workplans/")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            wp = results[0]
            assert isinstance(wp["project"], dict), f"v2 should return ProjectRef dict, got {type(wp['project'])}"

    def test_v1_project_workplans_returns_bare_id(self, setup):
        client, _, project, _, _, _, _, _ = setup
        resp = client.get(f"/v1/projects/{project.id}/workplans/")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            assert isinstance(results[0]["project"], str)


class TestWorkplanMilestonesReturnsV2:
    """Bug: WorkplanMilestonesView hardcoded MilestoneSerializer."""

    def test_v2_workplan_milestones_returns_refs(self, setup):
        client, _, _, workplan, _, _, _, _ = setup
        resp = client.get(f"/v2/workplans/{workplan.id}/milestones/")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            ms = results[0]
            assert isinstance(ms["workplan"], dict), f"v2 should return WorkplanRef dict, got {type(ms['workplan'])}"

    def test_v1_workplan_milestones_returns_bare_id(self, setup):
        client, _, _, workplan, _, _, _, _ = setup
        resp = client.get(f"/v1/workplans/{workplan.id}/milestones/")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            assert isinstance(results[0]["workplan"], str)


class TestAgentTasksReturnsV2:
    """Bug: AgentViewSet.tasks hardcoded TaskSerializer."""

    def test_v2_agent_tasks_returns_refs(self, setup):
        client, _, _, _, _, _, task_doing, agent = setup
        resp = client.get(f"/v2/agents/{agent.id}/tasks/")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            task = results[0]
            assert isinstance(task["project"], dict), f"v2 should return ProjectRef dict, got {type(task['project'])}"

    def test_v1_agent_tasks_returns_bare_id(self, setup):
        client, _, _, _, _, _, task_doing, agent = setup
        resp = client.get(f"/v1/agents/{agent.id}/tasks/")
        assert resp.status_code == 200
        results = resp.data.get("results", [])
        if results:
            assert isinstance(results[0]["project"], str)
