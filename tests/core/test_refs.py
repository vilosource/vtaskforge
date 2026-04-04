"""Step 3: Ref serializer and ActorRefField tests.

Tests that shared ref serializers produce correct shapes and ActorRefField
resolves User FK to discriminated {type: "agent"|"user"} objects.
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def human_user(db):
    from django.contrib.auth.models import User
    return User.objects.create_user("humanuser", password="pass")


@pytest.fixture
def agent_user(db):
    """Create a User + Agent pair."""
    from django.contrib.auth.models import User
    from agents.models import Agent

    user = User.objects.create_user("agent-exec-001", password="pass")
    Agent.objects.create(id="agent-exec-001", name="executor-1", user=user, pod_name="pod-abc-123")
    return user


@pytest.fixture
def agent_user_no_pod(db):
    """Agent with pod_name=None."""
    from django.contrib.auth.models import User
    from agents.models import Agent

    user = User.objects.create_user("agent-nopod", password="pass")
    Agent.objects.create(id="agent-nopod", name="nopod-agent", user=user, pod_name=None)
    return user


@pytest.fixture
def project(db, human_user):
    from projects.models import Project
    return Project.objects.create(name="TestProject", owner=human_user, created_by=human_user)


@pytest.fixture
def workplan(project, human_user):
    from workplans.models import Workplan
    return Workplan.objects.create(name="TestWP", project=project, owner=human_user, created_by=human_user)


@pytest.fixture
def milestone(workplan, human_user):
    from workplans.models import Milestone
    return Milestone.objects.create(name="TestMS", workplan=workplan, status="active", created_by=human_user)


@pytest.fixture
def task(project, workplan, milestone, human_user):
    from tasks.models import Task
    return Task.objects.create(
        title="TestTask", project=project, workplan=workplan,
        milestone=milestone, created_by=human_user,
    )


class TestRefSerializers:

    def test_project_ref_shape(self, project):
        """DoD #1"""
        from core.refs import ProjectRefSerializer
        data = ProjectRefSerializer(project).data
        assert data == {"id": project.id, "name": "TestProject"}

    def test_workplan_ref_shape(self, workplan):
        """DoD #2"""
        from core.refs import WorkplanRefSerializer
        data = WorkplanRefSerializer(workplan).data
        assert data == {"id": workplan.id, "name": "TestWP"}

    def test_milestone_ref_shape(self, milestone):
        """DoD #3"""
        from core.refs import MilestoneRefSerializer
        data = MilestoneRefSerializer(milestone).data
        assert data == {"id": milestone.id, "name": "TestMS", "status": "active"}

    def test_task_ref_shape(self, task):
        """DoD #4"""
        from core.refs import TaskRefSerializer
        data = TaskRefSerializer(task).data
        assert data == {"id": task.id, "title": "TestTask", "status": "draft"}


class TestActorRefField:

    def test_actor_ref_agent(self, agent_user):
        """DoD #5: User linked to Agent -> agent actor shape."""
        from core.refs import ActorRefField
        field = ActorRefField()
        result = field.to_representation(agent_user)
        assert result["type"] == "agent"
        assert result["id"] == "agent-exec-001"
        assert result["name"] == "executor-1"
        assert result["pod_name"] == "pod-abc-123"

    def test_actor_ref_agent_null_pod(self, agent_user_no_pod):
        """DoD #6: Agent with pod_name=None."""
        from core.refs import ActorRefField
        field = ActorRefField()
        result = field.to_representation(agent_user_no_pod)
        assert result["type"] == "agent"
        assert result["pod_name"] is None

    def test_actor_ref_human(self, human_user):
        """DoD #7: User without Agent -> user actor shape."""
        from core.refs import ActorRefField
        field = ActorRefField()
        result = field.to_representation(human_user)
        assert result["type"] == "user"
        assert result["id"] == str(human_user.pk)
        assert result["username"] == "humanuser"

    def test_actor_ref_null(self):
        """DoD #8: None input -> None."""
        from core.refs import ActorRefField
        field = ActorRefField()
        result = field.to_representation(None)
        assert result is None

    def test_ref_no_extra_fields(self, project, milestone):
        """DoD #9: Refs have exactly the right number of fields."""
        from core.refs import ProjectRefSerializer, MilestoneRefSerializer
        p_data = ProjectRefSerializer(project).data
        m_data = MilestoneRefSerializer(milestone).data
        assert len(p_data) == 2  # id, name
        assert len(m_data) == 3  # id, name, status

    def test_actor_ref_id_is_string(self, agent_user, human_user):
        """DoD #10: All actor IDs are strings."""
        from core.refs import ActorRefField
        field = ActorRefField()
        agent_result = field.to_representation(agent_user)
        human_result = field.to_representation(human_user)
        assert isinstance(agent_result["id"], str)
        assert isinstance(human_result["id"], str)
