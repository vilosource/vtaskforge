"""
Factory Boy factories for all vtaskforge models.
"""
import factory
from django.contrib.auth.models import User
from django.utils import timezone

from agents.models import Agent
from core.mixins import generate_nanoid
from events.models import TaskEvent
from links.models import Link
from projects.models import Project
from reviews.models import Review
from tasks.models import Note, Task
from variables.models import ProjectVariable, VariableAudit
from workplans.models import Milestone, Workplan


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f"Project {n}")
    status = "active"


class WorkplanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Workplan

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Workplan {n}")
    status = "active"


class MilestoneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Milestone

    workplan = factory.SubFactory(WorkplanFactory)
    name = factory.Sequence(lambda n: f"Milestone {n}")
    status = "active"


class TaskFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Task

    milestone = factory.SubFactory(MilestoneFactory)
    workplan = factory.LazyAttribute(lambda o: o.milestone.workplan)
    project = factory.LazyAttribute(lambda o: o.milestone.workplan.project)
    title = factory.Sequence(lambda n: f"Task {n}")
    status = "draft"


class BacklogTaskFactory(factory.django.DjangoModelFactory):
    """Factory for backlog tasks (no workplan, no milestone)."""
    class Meta:
        model = Task

    project = factory.SubFactory(ProjectFactory)
    milestone = None
    workplan = None
    title = factory.Sequence(lambda n: f"Backlog Task {n}")
    status = "draft"


class AgentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Agent
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Agent {n}")
    tags = factory.List([])
    status = "online"

    @factory.post_generation
    def link_user(self, create, extracted, **kwargs):
        """Create a User and link it to the Agent via FK."""
        if not create:
            return
        user = User.objects.create_user(username=self.id)
        self.user = user
        self.save(update_fields=["user"])


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
    actor = factory.LazyFunction(lambda: User.objects.create_user(
        username=f"note-actor-{generate_nanoid()[:8]}"
    ))


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    task = factory.SubFactory(TaskFactory)
    decision = "approved"
    reviewer = factory.LazyFunction(lambda: User.objects.create_user(
        username=f"reviewer-{generate_nanoid()[:8]}"
    ))
    reviewer_type = "human"


class TaskEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TaskEvent

    task = factory.SubFactory(TaskFactory)
    event_type = "status_changed"
    data = factory.Dict({"from": "draft", "to": "todo"})
    trigger_source = "test"
    actor = None


class ProjectVariableFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectVariable

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"VAR_{n}")
    role = "executor"
    scope = "project"
    required = True


class VariableAuditFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VariableAudit

    project = factory.SubFactory(ProjectFactory)
    task = factory.SubFactory(TaskFactory)
    timestamp = factory.LazyFunction(timezone.now)
    variable_name = factory.Sequence(lambda n: f"VAR_{n}")
    variable_scope = "project"
    vault_path = factory.LazyAttribute(
        lambda o: f"secret/apps/vtaskforge/dev/projects/{o.project.id}/executor/{o.variable_name}"
    )
    vault_version = 1
    result = "success"
    size_bytes = 47
    duration_ms = 12
    controller_id = "controller-0"
