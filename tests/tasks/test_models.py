import pytest

from tasks.models import Task
from workplans.models import Phase, Workplan


def make_workplan(**kwargs):
    defaults = {"name": "Test Workplan"}
    defaults.update(kwargs)
    return Workplan.objects.create(**defaults)


def make_phase(workplan=None, **kwargs):
    if workplan is None:
        workplan = make_workplan()
    defaults = {"name": "Test Phase", "workplan": workplan}
    defaults.update(kwargs)
    return Phase.objects.create(**defaults)


@pytest.mark.django_db
class TestTaskModel:
    def test_create_task_minimal(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="My Task", phase=phase, workplan=wp)
        assert task.id is not None
        assert task.title == "My Task"

    def test_status_defaults_to_draft(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="Task", phase=phase, workplan=wp)
        assert task.status == "draft"

    def test_acceptance_criteria_defaults_to_empty_list(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="Task", phase=phase, workplan=wp)
        assert task.acceptance_criteria == []

    def test_requires_defaults_to_empty_list(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="Task", phase=phase, workplan=wp)
        assert task.requires == []

    def test_review_flags_default_to_none(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="Task", phase=phase, workplan=wp)
        assert task.needs_review_before_start is None
        assert task.needs_review_on_completion is None

    def test_claim_fields_default_to_none(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="Task", phase=phase, workplan=wp)
        assert task.claimed_by is None
        assert task.claimed_at is None
        assert task.claim_timeout is None
        assert task.claim_expires_at is None

    def test_cascade_delete_from_phase(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="Task", phase=phase, workplan=wp)
        task_id = task.id
        phase.delete()
        assert not Task.objects.filter(id=task_id).exists()

    def test_cascade_delete_from_workplan(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="Task", phase=phase, workplan=wp)
        task_id = task.id
        wp.delete()
        assert not Task.objects.filter(id=task_id).exists()

    def test_str_returns_title(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task = Task.objects.create(title="My Task Title", phase=phase, workplan=wp)
        assert str(task) == "My Task Title"

    def test_nanoid_primary_key(self):
        wp = make_workplan()
        phase = make_phase(workplan=wp)
        task1 = Task.objects.create(title="Task 1", phase=phase, workplan=wp)
        task2 = Task.objects.create(title="Task 2", phase=phase, workplan=wp)
        assert task1.id != task2.id
        assert len(task1.id) == 21
        assert len(task2.id) == 21
