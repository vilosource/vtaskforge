"""
Unit tests for get_effective_review_flags cascade logic.

Cascade order: task -> phase -> workplan
Task flag=False OVERRIDES phase/workplan flag=True (explicit False is not null).
"""
from unittest.mock import MagicMock

import pytest

from tasks.review_policy import get_effective_review_flags


def make_task(
    task_before_start=None,
    task_on_completion=None,
    phase_before_start=None,
    phase_on_completion=None,
    workplan_before_start=False,
    workplan_on_completion=False,
):
    """Build a mock task with the given flag values."""
    workplan = MagicMock()
    workplan.default_needs_review_before_start = workplan_before_start
    workplan.default_needs_review_on_completion = workplan_on_completion

    phase = MagicMock()
    phase.default_needs_review_before_start = phase_before_start
    phase.default_needs_review_on_completion = phase_on_completion

    task = MagicMock()
    task.needs_review_before_start = task_before_start
    task.needs_review_on_completion = task_on_completion
    task.phase = phase
    task.workplan = workplan

    return task


# ---------------------------------------------------------------------------
# before_start cascade
# ---------------------------------------------------------------------------

class TestBeforeStartCascade:
    def test_task_true_overrides_all(self):
        task = make_task(
            task_before_start=True,
            phase_before_start=False,
            workplan_before_start=False,
        )
        before_start, _ = get_effective_review_flags(task)
        assert before_start is True

    def test_task_false_overrides_phase_true(self):
        """Explicit False on task must win over phase=True."""
        task = make_task(
            task_before_start=False,
            phase_before_start=True,
            workplan_before_start=True,
        )
        before_start, _ = get_effective_review_flags(task)
        assert before_start is False

    def test_task_none_falls_through_to_phase_true(self):
        task = make_task(
            task_before_start=None,
            phase_before_start=True,
            workplan_before_start=False,
        )
        before_start, _ = get_effective_review_flags(task)
        assert before_start is True

    def test_task_none_falls_through_to_phase_false(self):
        task = make_task(
            task_before_start=None,
            phase_before_start=False,
            workplan_before_start=True,
        )
        before_start, _ = get_effective_review_flags(task)
        assert before_start is False

    def test_task_none_phase_none_falls_through_to_workplan_true(self):
        task = make_task(
            task_before_start=None,
            phase_before_start=None,
            workplan_before_start=True,
        )
        before_start, _ = get_effective_review_flags(task)
        assert before_start is True

    def test_task_none_phase_none_falls_through_to_workplan_false(self):
        task = make_task(
            task_before_start=None,
            phase_before_start=None,
            workplan_before_start=False,
        )
        before_start, _ = get_effective_review_flags(task)
        assert before_start is False

    def test_all_none_defaults_to_false(self):
        """When workplan is False (its default), result is False."""
        task = make_task(
            task_before_start=None,
            phase_before_start=None,
            workplan_before_start=False,
        )
        before_start, _ = get_effective_review_flags(task)
        assert before_start is False


# ---------------------------------------------------------------------------
# on_completion cascade
# ---------------------------------------------------------------------------

class TestOnCompletionCascade:
    def test_task_true_overrides_all(self):
        task = make_task(
            task_on_completion=True,
            phase_on_completion=False,
            workplan_on_completion=False,
        )
        _, on_completion = get_effective_review_flags(task)
        assert on_completion is True

    def test_task_false_overrides_phase_true(self):
        task = make_task(
            task_on_completion=False,
            phase_on_completion=True,
            workplan_on_completion=True,
        )
        _, on_completion = get_effective_review_flags(task)
        assert on_completion is False

    def test_task_none_falls_through_to_phase_true(self):
        task = make_task(
            task_on_completion=None,
            phase_on_completion=True,
            workplan_on_completion=False,
        )
        _, on_completion = get_effective_review_flags(task)
        assert on_completion is True

    def test_task_none_phase_none_falls_through_to_workplan_true(self):
        task = make_task(
            task_on_completion=None,
            phase_on_completion=None,
            workplan_on_completion=True,
        )
        _, on_completion = get_effective_review_flags(task)
        assert on_completion is True

    def test_task_none_phase_none_workplan_false_returns_false(self):
        task = make_task(
            task_on_completion=None,
            phase_on_completion=None,
            workplan_on_completion=False,
        )
        _, on_completion = get_effective_review_flags(task)
        assert on_completion is False


# ---------------------------------------------------------------------------
# Independence of the two flags
# ---------------------------------------------------------------------------

class TestFlagIndependence:
    def test_before_start_and_on_completion_independent(self):
        """before_start from task, on_completion from workplan."""
        task = make_task(
            task_before_start=True,
            task_on_completion=None,
            phase_before_start=None,
            phase_on_completion=None,
            workplan_before_start=False,
            workplan_on_completion=True,
        )
        before_start, on_completion = get_effective_review_flags(task)
        assert before_start is True
        assert on_completion is True

    def test_returns_tuple_of_two_bools(self):
        task = make_task()
        result = get_effective_review_flags(task)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], bool)
