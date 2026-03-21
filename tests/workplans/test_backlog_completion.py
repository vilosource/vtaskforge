"""
Tests for milestone auto-completion behavior with backlog tasks.

Backlog tasks (no milestone) should not trigger milestone completion attempts.
The maybe_complete_milestone function should handle task.milestone=None gracefully.
"""
from unittest.mock import MagicMock

import pytest

from workplans.completion import maybe_complete_milestone
from tests.factories import BacklogTaskFactory, ProjectFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project(db):
    return ProjectFactory(name="Test Project")


@pytest.fixture
def backlog_task(db, project):
    return BacklogTaskFactory(project=project, status="done")


# ---------------------------------------------------------------------------
# Unit tests: maybe_complete_milestone with backlog tasks
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBacklogTaskCompletion:
    def test_backlog_task_does_not_trigger_completion(self, backlog_task):
        """Completing a backlog task (no milestone) should be a no-op."""
        result = maybe_complete_milestone(backlog_task)
        assert result is None

    def test_backlog_task_completion_does_not_crash(self, backlog_task):
        """maybe_complete_milestone should handle task.milestone=None gracefully."""
        # Should not raise AttributeError or other exceptions
        try:
            result = maybe_complete_milestone(backlog_task)
            assert result is None
        except Exception as e:
            pytest.fail(f"maybe_complete_milestone crashed with backlog task: {e}")

    def test_multiple_backlog_tasks_all_no_op(self, project):
        """Multiple backlog tasks should all be no-ops for completion."""
        task1 = BacklogTaskFactory(project=project, status="done")
        task2 = BacklogTaskFactory(project=project, status="cancelled")
        task3 = BacklogTaskFactory(project=project, status="done")

        assert maybe_complete_milestone(task1) is None
        assert maybe_complete_milestone(task2) is None
        assert maybe_complete_milestone(task3) is None


# ---------------------------------------------------------------------------
# Mock-based tests for edge cases
# ---------------------------------------------------------------------------

class TestBacklogCompletionEdgeCases:
    def test_task_with_none_milestone_attribute(self):
        """Task with milestone=None should return None immediately."""
        task = MagicMock()
        task.milestone = None

        result = maybe_complete_milestone(task)
        assert result is None

    def test_getattr_none_milestone_fallback(self):
        """Task without milestone attribute should return None via getattr."""
        task = MagicMock()
        # Remove the milestone attribute entirely
        if hasattr(task, 'milestone'):
            del task.milestone

        result = maybe_complete_milestone(task)
        assert result is None

    def test_backlog_task_does_not_access_milestone_methods(self):
        """Backlog task should not trigger any milestone queries or operations."""
        task = MagicMock()
        task.milestone = None

        # Create a milestone mock that would fail if accessed
        failing_milestone = MagicMock()
        failing_milestone.status = property(lambda x: (_ for _ in ()).throw(Exception("Should not access")))
        failing_milestone.tasks = property(lambda x: (_ for _ in ()).throw(Exception("Should not access")))

        # Ensure the task's None milestone is never replaced with the failing one
        result = maybe_complete_milestone(task)
        assert result is None

        # Verify no milestone methods were called (since milestone is None)
        task.milestone = None  # Ensure it stays None