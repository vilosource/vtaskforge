"""Step 6: v2 Agent serializer tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from agents.models import Agent
    from projects.models import Project
    from tasks.models import Task

    user = User.objects.create_user("agtv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    agent_user = User.objects.create_user("agent-v2-test", password="pass")
    agent = Agent.objects.create(id="agent-v2-test", name="v2-executor", user=agent_user, pod_name="pod-v2")

    project = Project.objects.create(name="AgtProj", owner=user, created_by=user)
    task = Task.objects.create(
        title="AgentTask", project=project, status="doing",
        claimed_by=agent_user, created_by=user,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, agent, task


class TestAgentV2:
    def test_v2_agent_current_task_is_task_ref(self, setup):
        """DoD #1"""
        client, agent, task = setup
        resp = client.get(f"/v2/agents/{agent.id}/")
        assert resp.status_code == 200
        ct = resp.data["current_task"]
        assert isinstance(ct, dict)
        assert ct["id"] == task.id
        assert ct["title"] == "AgentTask"
        assert ct["status"] == "doing"

    def test_v2_agent_current_task_null(self, setup):
        """DoD #2"""
        from agents.models import Agent
        from django.contrib.auth.models import User
        client, _, _ = setup
        u = User.objects.create_user("idle-agent", password="pass")
        Agent.objects.create(id="idle-agent", name="idle", user=u)
        resp = client.get("/v2/agents/idle-agent/")
        assert resp.data["current_task"] is None

    def test_v1_agent_unchanged(self, setup):
        """DoD #3"""
        client, agent, _ = setup
        resp = client.get(f"/v1/agents/{agent.id}/")
        assert resp.status_code == 200
        # v1 current_task is also a dict but NOT from TaskRefSerializer — same shape coincidence
        # Main check: no "permissions" field in v1
        assert "permissions" not in resp.data
