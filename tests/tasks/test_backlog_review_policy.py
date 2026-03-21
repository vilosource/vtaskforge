"""
Tests for review policy cascading with backlog tasks (no milestone/workplan).

Tests the behavior of get_effective_review_flags with tasks that have:
- No milestone and no workplan (pure backlog tasks)
- Workplan but no milestone (workplan-level tasks)
- Task-level review flags that override any cascading
"""
from unittest.mock import MagicMock

import pytest

from tasks.review_policy import get_effective_review_flags


def make_backlog_task(
    task_before_start=None,
    task_on_completion=None,
    workplan_before_start=False,
    workplan_on_completion=False,
    has_workplan=False,
):
    """Build a mock backlog task with optional workplan."""
    task = MagicMock()
    task.needs_review_before_start = task_before_start
    task.needs_review_on_completion = task_on_completion
    task.milestone = None  # Backlog tasks have no milestone

    if has_workplan:
        workplan = MagicMock()
        workplan.default_needs_review_before_start = workplan_before_start
        workplan.default_needs_review_on_completion = workplan_on_completion
        task.workplan = workplan
    else:
        task.workplan = None

    return task


# ---------------------------------------------------------------------------
# Pure backlog tasks (no milestone, no workplan)
# ---------------------------------------------------------------------------

class TestPureBacklogTasks:
    def test_backlog_task_no_review_flags_defaults_to_false(self):
        """Backlog task with no review flags should default to (False, False)."""
        task = make_backlog_task()
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is False
        assert on_completion is False

    def test_backlog_task_with_explicit_review_before_start(self):
        """Task-level review_before_start should override even with no cascade."""
        task = make_backlog_task(task_before_start=True)
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is True
        assert on_completion is False

    def test_backlog_task_with_explicit_review_on_completion(self):
        """Task-level review_on_completion should override even with no cascade."""
        task = make_backlog_task(task_on_completion=True)
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is False
        assert on_completion is True

    def test_backlog_task_explicit_false_overrides_nothing(self):
        """Explicit False at task level should still result in False with no cascade."""
        task = make_backlog_task(task_before_start=False, task_on_completion=False)
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is False
        assert on_completion is False


# ---------------------------------------------------------------------------
# Workplan-only tasks (no milestone, but has workplan)
# ---------------------------------------------------------------------------

class TestWorkplanOnlyTasks:
    def test_task_with_workplan_no_milestone_cascades_to_workplan(self):
        """Task with workplan but no milestone should cascade to workplan defaults."""
        task = make_backlog_task(
            has_workplan=True,
            workplan_before_start=True,
            workplan_on_completion=True
        )
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is True
        assert on_completion is True

    def test_task_overrides_workplan_with_explicit_false(self):
        """Task-level False should override workplan True."""
        task = make_backlog_task(
            task_before_start=False,
            task_on_completion=False,
            has_workplan=True,
            workplan_before_start=True,
            workplan_on_completion=True
        )
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is False
        assert on_completion is False

    def test_task_none_falls_through_to_workplan_false(self):
        """Task None should fall through to workplan False."""
        task = make_backlog_task(
            has_workplan=True,
            workplan_before_start=False,
            workplan_on_completion=False
        )
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is False
        assert on_completion is False

    def test_mixed_task_and_workplan_flags(self):
        """Task-level before_start True, fall through to workplan for on_completion."""
        task = make_backlog_task(
            task_before_start=True,
            task_on_completion=None,  # Falls through
            has_workplan=True,
            workplan_before_start=False,  # Ignored due to task override
            workplan_on_completion=True   # Used for on_completion
        )
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is True   # From task
        assert on_completion is True  # From workplan


# ---------------------------------------------------------------------------
# Error handling and edge cases
# ---------------------------------------------------------------------------

class TestBacklogTaskErrorHandling:
    def test_handles_none_milestone_gracefully(self):
        """Should not crash when task.milestone is None."""
        task = make_backlog_task()
        # Should not raise AttributeError or other exceptions
        result = get_effective_review_flags(task)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], bool)

    def test_handles_none_workplan_gracefully(self):
        """Should not crash when task.workplan is None."""
        task = make_backlog_task(has_workplan=False)
        # Should not raise AttributeError or other exceptions
        result = get_effective_review_flags(task)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], bool)