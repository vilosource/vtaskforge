"""
Factory Boy factories for all vtaskforge models.
"""
import factory

from agents.models import Agent
from core.mixins import generate_nanoid
from events.models import TaskEvent
from links.models import Link
from projects.models import Project
from reviews.models import Review
from tasks.models import Note, Task
from workplans.models import Milestone, Workplan


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f"Project {n}")
    status = "active"


class WorkplanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Workplan

    name = factory.Sequence(lambda n: f"Workplan {n}")
    status = "active"


class MilestoneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Milestone

    workplan = factory.SubFactory(WorkplanFactory)
    name = factory.Sequence(lambda n: f"Milestone {n}")
    status = "pending"


class TaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Task

    milestone = factory.SubFactory(MilestoneFactory)
    workplan = factory.LazyAttribute(lambda o: o.milestone.workplan)
    title = factory.Sequence(lambda n: f"Task {n}")
    status = "draft"


class AgentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Agent

    name = factory.Sequence(lambda n: f"Agent {n}")
    tags = factory.List([])
    status = "online"


class LinkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Link

    source_type = "task"
    source_id = factory.LazyFunction(generate_nanoid)
    target_type = "task"
    target_id = factory.LazyFunction(generate_nanoid)
    link_type = "depends_on"


class NoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Note

    task = factory.SubFactory(TaskFactory)
    text = "Test note"
    actor_id = "test-actor"


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    task = factory.SubFactory(TaskFactory)
    decision = "approved"
    reviewer_id = "test-reviewer"
    reviewer_type = "human"


class TaskEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TaskEvent

    task = factory.SubFactory(TaskFactory)
    event_type = "status_changed"
    data = factory.Dict({"from": "draft", "to": "todo"})
