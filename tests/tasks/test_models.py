import pytest

from tasks.models import Task
from tests.factories import TaskFactory, WorkplanFactory, MilestoneFactory


@pytest.mark.django_db
class TestTaskModel:
    def test_create_task_minimal(self):
        task = TaskFactory(title="My Task")
        assert task.id is not None
        assert task.title == "My Task"

    def test_status_defaults_to_draft(self):
        task = TaskFactory()
        assert task.status == "draft"

    def test_acceptance_criteria_defaults_to_empty_list(self):
        task = TaskFactory()
        assert task.acceptance_criteria == []

    def test_requires_defaults_to_empty_list(self):
        task = TaskFactory()
        assert task.requires == []

    def test_review_flags_default_to_none(self):
        task = TaskFactory()
        assert task.needs_review_before_start is None
        assert task.needs_review_on_completion is None

    def test_claim_fields_default_to_none(self):
        task = TaskFactory()
        assert task.claimed_by is None
        assert task.claimed_at is None
        assert task.claim_timeout is None
        assert task.claim_expires_at is None

    def test_cascade_delete_from_phase(self):
        task = TaskFactory()
        task_id = task.id
        task.milestone.delete()
        assert not Task.objects.filter(id=task_id).exists()

    def test_cascade_delete_from_workplan(self):
        task = TaskFactory()
        task_id = task.id
        task.workplan.delete()
        assert not Task.objects.filter(id=task_id).exists()

    def test_str_returns_title(self):
        task = TaskFactory(title="My Task Title")
        assert str(task) == "My Task Title"

    def test_nanoid_primary_key(self):
        wp = WorkplanFactory()
        phase = MilestoneFactory(workplan=wp)
        task1 = TaskFactory(title="Task 1", milestone=phase, workplan=wp)
        task2 = TaskFactory(title="Task 2", milestone=phase, workplan=wp)
        assert task1.id != task2.id
        assert len(task1.id) == 21
        assert len(task2.id) == 21
