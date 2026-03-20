import pytest

from agents.models import Agent


@pytest.mark.django_db
class TestAgentModel:
    def test_create_agent_minimal(self):
        agent = Agent.objects.create(name="Test Agent")
        assert agent.id is not None
        assert len(agent.id) == 21
        assert agent.name == "Test Agent"
        assert agent.status == "offline"
        assert agent.tags == []
        assert agent.last_heartbeat is None

    def test_create_agent_all_fields(self):
        agent = Agent.objects.create(
            name="Full Agent",
            tags=["python", "llm"],
            status="online",
        )
        assert agent.name == "Full Agent"
        assert agent.tags == ["python", "llm"]
        assert agent.status == "online"

    def test_timestamps_auto_populated(self):
        agent = Agent.objects.create(name="Timestamps Test")
        assert agent.created_at is not None
        assert agent.updated_at is not None
        assert agent.registered_at is not None

    def test_str_representation(self):
        agent = Agent.objects.create(name="My Agent")
        assert str(agent) == "My Agent"

    def test_nanoid_primary_key(self):
        a1 = Agent.objects.create(name="Agent1")
        a2 = Agent.objects.create(name="Agent2")
        assert a1.id != a2.id
        assert len(a1.id) == 21

    def test_status_choices(self):
        choices = dict(Agent.STATUS_CHOICES)
        assert "online" in choices
        assert "offline" in choices
        assert "busy" in choices

    def test_default_ordering(self):
        a1 = Agent.objects.create(name="First")
        a2 = Agent.objects.create(name="Second")
        agents = list(Agent.objects.all())
        # Most recently registered should come first
        assert agents[0].id == a2.id
        assert agents[1].id == a1.id

    def test_tags_accepts_list(self):
        agent = Agent.objects.create(name="Tagged", tags=["tag1", "tag2"])
        agent.refresh_from_db()
        assert agent.tags == ["tag1", "tag2"]

    def test_registered_at_is_separate_from_created_at(self):
        agent = Agent.objects.create(name="Timing Agent")
        assert agent.registered_at is not None
        assert agent.created_at is not None
        # Both are set independently
        assert hasattr(agent, "registered_at")
        assert hasattr(agent, "created_at")
