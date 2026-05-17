import pytest

from tasks.exceptions import InvalidTransition
from tasks.state_machine import (
    TERMINAL_STATUSES,
    NON_TERMINAL_STATUSES,
    VALID_TRANSITIONS,
    get_valid_transitions,
    perform_transition,
    validate_transition,
)
from tests.factories import TaskFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_task(status="draft", **kwargs):
    return TaskFactory(status=status, **kwargs)


# ---------------------------------------------------------------------------
# Unit tests — no DB required
# ---------------------------------------------------------------------------

class TestInvalidTransitionException:
    def test_attributes_are_stored(self):
        exc = InvalidTransition("draft", "doing", ["todo", "cancelled"])
        assert exc.current_status == "draft"
        assert exc.requested_status == "doing"
        assert exc.valid_transitions == ["todo", "cancelled"]

    def test_message_contains_statuses(self):
        exc = InvalidTransition("done", "todo", [])
        assert "done" in str(exc)
        assert "todo" in str(exc)

    def test_is_exception_subclass(self):
        assert issubclass(InvalidTransition, Exception)


class TestValidTransitionsStructure:
    def test_all_11_statuses_are_keys(self):
        expected = {
            "draft", "pending_start_review", "todo", "doing",
            "pending_completion_review", "changes_requested",
            "needs_attention", "blocked", "deferred",
            "cancelled", "done",
        }
        assert set(VALID_TRANSITIONS.keys()) == expected

    def test_terminal_statuses_have_empty_lists(self):
        for status in TERMINAL_STATUSES:
            assert VALID_TRANSITIONS[status] == [], f"{status} should have no outgoing transitions"

    def test_cancelled_reachable_from_all_non_terminal(self):
        for status in NON_TERMINAL_STATUSES:
            assert "cancelled" in VALID_TRANSITIONS[status], \
                f"'cancelled' must be reachable from '{status}'"

    def test_deferred_reachable_from_all_non_terminal(self):
        # Every non-terminal status except 'deferred' itself can transition to 'deferred'
        for status in NON_TERMINAL_STATUSES - {"deferred"}:
            assert "deferred" in VALID_TRANSITIONS[status], \
                f"'deferred' must be reachable from '{status}'"


class TestGetValidTransitions:
    def test_draft_transitions(self):
        result = get_valid_transitions("draft")
        assert set(result) == {"pending_start_review", "todo", "cancelled", "deferred"}

    def test_pending_start_review_transitions(self):
        result = get_valid_transitions("pending_start_review")
        assert set(result) == {"todo", "changes_requested", "cancelled", "deferred"}

    def test_todo_transitions(self):
        result = get_valid_transitions("todo")
        assert set(result) == {"doing", "blocked", "cancelled", "deferred"}

    def test_doing_transitions(self):
        result = get_valid_transitions("doing")
        assert set(result) == {
            "todo",
            "pending_completion_review", "done", "needs_attention",
            "blocked", "cancelled", "deferred",
        }

    def test_pending_completion_review_transitions(self):
        result = get_valid_transitions("pending_completion_review")
        # R3: + needs_attention (review-lease-expired escalation to the
        # human terminal; see docs/review-phase-lease-DESIGN.md).
        assert set(result) == {
            "done", "changes_requested", "cancelled", "deferred",
            "needs_attention",
        }

    def test_changes_requested_transitions(self):
        result = get_valid_transitions("changes_requested")
        assert set(result) == {
            "doing",
            "pending_start_review", "pending_completion_review",
            "draft", "cancelled", "deferred",
        }

    def test_needs_attention_transitions(self):
        result = get_valid_transitions("needs_attention")
        assert set(result) == {"draft", "todo", "cancelled", "deferred"}

    def test_blocked_transitions(self):
        result = get_valid_transitions("blocked")
        assert set(result) == {"todo", "doing", "cancelled", "deferred"}

    def test_deferred_transitions(self):
        result = get_valid_transitions("deferred")
        assert set(result) == {"todo", "cancelled"}

    def test_cancelled_transitions(self):
        assert get_valid_transitions("cancelled") == []

    def test_done_transitions(self):
        assert get_valid_transitions("done") == []

    def test_unknown_status_returns_empty(self):
        assert get_valid_transitions("nonexistent") == []


# ---------------------------------------------------------------------------
# DB-backed tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestValidateTransition:
    # --- Valid transitions ---

    def test_draft_to_pending_start_review(self):
        task = make_task("draft")
        validate_transition(task, "pending_start_review")  # should not raise

    def test_draft_to_todo(self):
        task = make_task("draft")
        validate_transition(task, "todo")

    def test_draft_to_cancelled(self):
        task = make_task("draft")
        validate_transition(task, "cancelled")

    def test_draft_to_deferred(self):
        task = make_task("draft")
        validate_transition(task, "deferred")

    def test_pending_start_review_to_todo(self):
        task = make_task("pending_start_review")
        validate_transition(task, "todo")

    def test_pending_start_review_to_changes_requested(self):
        task = make_task("pending_start_review")
        validate_transition(task, "changes_requested")

    def test_pending_start_review_to_cancelled(self):
        task = make_task("pending_start_review")
        validate_transition(task, "cancelled")

    def test_pending_start_review_to_deferred(self):
        task = make_task("pending_start_review")
        validate_transition(task, "deferred")

    def test_todo_to_doing(self):
        task = make_task("todo")
        validate_transition(task, "doing")

    def test_todo_to_blocked(self):
        task = make_task("todo")
        validate_transition(task, "blocked")

    def test_todo_to_cancelled(self):
        task = make_task("todo")
        validate_transition(task, "cancelled")

    def test_todo_to_deferred(self):
        task = make_task("todo")
        validate_transition(task, "deferred")

    def test_doing_to_todo(self):
        task = make_task("doing")
        validate_transition(task, "todo")  # unclaim path

    def test_doing_to_pending_completion_review(self):
        task = make_task("doing")
        validate_transition(task, "pending_completion_review")

    def test_doing_to_done(self):
        task = make_task("doing")
        validate_transition(task, "done")

    def test_doing_to_needs_attention(self):
        task = make_task("doing")
        validate_transition(task, "needs_attention")

    def test_doing_to_blocked(self):
        task = make_task("doing")
        validate_transition(task, "blocked")

    def test_doing_to_cancelled(self):
        task = make_task("doing")
        validate_transition(task, "cancelled")

    def test_doing_to_deferred(self):
        task = make_task("doing")
        validate_transition(task, "deferred")

    def test_pending_completion_review_to_done(self):
        task = make_task("pending_completion_review")
        validate_transition(task, "done")

    def test_pending_completion_review_to_changes_requested(self):
        task = make_task("pending_completion_review")
        validate_transition(task, "changes_requested")

    def test_pending_completion_review_to_cancelled(self):
        task = make_task("pending_completion_review")
        validate_transition(task, "cancelled")

    def test_pending_completion_review_to_deferred(self):
        task = make_task("pending_completion_review")
        validate_transition(task, "deferred")

    def test_changes_requested_to_pending_start_review(self):
        task = make_task("changes_requested")
        validate_transition(task, "pending_start_review")

    def test_changes_requested_to_pending_completion_review(self):
        task = make_task("changes_requested")
        validate_transition(task, "pending_completion_review")

    def test_changes_requested_to_draft(self):
        task = make_task("changes_requested")
        validate_transition(task, "draft")

    def test_changes_requested_to_cancelled(self):
        task = make_task("changes_requested")
        validate_transition(task, "cancelled")

    def test_changes_requested_to_deferred(self):
        task = make_task("changes_requested")
        validate_transition(task, "deferred")

    def test_needs_attention_to_draft(self):
        task = make_task("needs_attention")
        validate_transition(task, "draft")

    def test_needs_attention_to_todo(self):
        task = make_task("needs_attention")
        validate_transition(task, "todo")

    def test_needs_attention_to_cancelled(self):
        task = make_task("needs_attention")
        validate_transition(task, "cancelled")

    def test_needs_attention_to_deferred(self):
        task = make_task("needs_attention")
        validate_transition(task, "deferred")

    def test_blocked_to_todo(self):
        task = make_task("blocked")
        validate_transition(task, "todo")

    def test_blocked_to_doing(self):
        task = make_task("blocked")
        validate_transition(task, "doing")

    def test_blocked_to_cancelled(self):
        task = make_task("blocked")
        validate_transition(task, "cancelled")

    def test_blocked_to_deferred(self):
        task = make_task("blocked")
        validate_transition(task, "deferred")

    def test_deferred_to_todo(self):
        task = make_task("deferred")
        validate_transition(task, "todo")

    def test_deferred_to_cancelled(self):
        task = make_task("deferred")
        validate_transition(task, "cancelled")

    # --- Invalid transitions ---

    def test_draft_to_doing_is_invalid(self):
        task = make_task("draft")
        with pytest.raises(InvalidTransition) as exc_info:
            validate_transition(task, "doing")
        assert exc_info.value.current_status == "draft"
        assert exc_info.value.requested_status == "doing"

    def test_done_to_todo_is_invalid(self):
        task = make_task("done")
        with pytest.raises(InvalidTransition):
            validate_transition(task, "todo")

    def test_cancelled_to_todo_is_invalid(self):
        task = make_task("cancelled")
        with pytest.raises(InvalidTransition):
            validate_transition(task, "todo")

    def test_done_to_draft_is_invalid(self):
        task = make_task("done")
        with pytest.raises(InvalidTransition):
            validate_transition(task, "draft")

    def test_todo_to_done_is_invalid(self):
        task = make_task("todo")
        with pytest.raises(InvalidTransition):
            validate_transition(task, "done")

    def test_draft_to_needs_attention_is_invalid(self):
        task = make_task("draft")
        with pytest.raises(InvalidTransition):
            validate_transition(task, "needs_attention")

    def test_deferred_to_draft_is_invalid(self):
        task = make_task("deferred")
        with pytest.raises(InvalidTransition):
            validate_transition(task, "draft")

    def test_invalid_transition_carries_valid_list(self):
        task = make_task("todo")
        with pytest.raises(InvalidTransition) as exc_info:
            validate_transition(task, "done")
        exc = exc_info.value
        assert set(exc.valid_transitions) == {"doing", "blocked", "cancelled", "deferred"}


@pytest.mark.django_db
class TestPerformTransition:
    def test_updates_task_status(self):
        task = make_task("draft")
        result = perform_transition(task, "todo")
        assert result.status == "todo"

    def test_saves_to_db(self):
        task = make_task("draft")
        perform_transition(task, "todo")
        task.refresh_from_db()
        assert task.status == "todo"

    def test_returns_task(self):
        task = make_task("draft")
        result = perform_transition(task, "todo")
        assert result.pk == task.pk

    def test_raises_on_invalid_transition(self):
        task = make_task("draft")
        with pytest.raises(InvalidTransition):
            perform_transition(task, "doing")

    def test_db_not_updated_on_invalid_transition(self):
        task = make_task("draft")
        with pytest.raises(InvalidTransition):
            perform_transition(task, "doing")
        task.refresh_from_db()
        assert task.status == "draft"

    def test_trigger_source_param_accepted(self):
        task = make_task("todo")
        result = perform_transition(task, "doing", trigger_source="claim")
        assert result.status == "doing"

    def test_chain_of_transitions(self):
        task = make_task("draft")
        perform_transition(task, "todo")
        perform_transition(task, "doing")
        perform_transition(task, "done")
        task.refresh_from_db()
        assert task.status == "done"

    def test_terminal_done_cannot_transition(self):
        task = make_task("doing")
        perform_transition(task, "done")
        with pytest.raises(InvalidTransition):
            perform_transition(task, "todo")

    def test_terminal_cancelled_cannot_transition(self):
        task = make_task("draft")
        perform_transition(task, "cancelled")
        with pytest.raises(InvalidTransition):
            perform_transition(task, "todo")


# ---------------------------------------------------------------------------
# Guard framework
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGuardFramework:
    """Tests for the entry/exit/transition guard system."""

    def test_transition_with_no_guards_still_works(self):
        """Transitions without any guards should work as before."""
        task = make_task("doing")
        perform_transition(task, "needs_attention")
        assert task.status == "needs_attention"

    def test_guard_violation_prevents_transition(self):
        """A guard that raises GuardViolation should block the transition."""
        from tasks.exceptions import GuardViolation
        # A task without a workplan should not be able to reach todo
        task = make_task("draft", workplan=None)
        with pytest.raises(GuardViolation):
            perform_transition(task, "todo")
        task.refresh_from_db()
        assert task.status == "draft"

    def test_guard_violation_has_structured_info(self):
        """GuardViolation should carry guard name and message."""
        from tasks.exceptions import GuardViolation
        task = make_task("draft", workplan=None)
        with pytest.raises(GuardViolation) as exc_info:
            perform_transition(task, "todo")
        assert exc_info.value.guard_name is not None
        assert len(str(exc_info.value)) > 0

    def test_entry_guard_fires_on_any_transition_into_status(self):
        """An entry guard for 'todo' fires regardless of source status."""
        from tasks.exceptions import GuardViolation
        # needs_attention -> todo should also be blocked without workplan
        task = make_task("needs_attention", workplan=None)
        with pytest.raises(GuardViolation):
            perform_transition(task, "todo")

    def test_exit_guard_fires_on_any_transition_from_status(self):
        """An exit guard for 'draft' fires regardless of target status."""
        from tests.factories import MilestoneFactory, WorkplanFactory
        wp = WorkplanFactory()
        ms = MilestoneFactory(workplan=wp, status="pending")
        task = make_task("draft", workplan=wp, milestone=ms)
        from tasks.exceptions import GuardViolation
        with pytest.raises(GuardViolation):
            perform_transition(task, "cancelled")

    def test_multiple_guards_all_checked(self):
        """When multiple guards exist, all are checked."""
        from tasks.exceptions import GuardViolation
        from tests.factories import MilestoneFactory, WorkplanFactory
        wp = WorkplanFactory()
        ms = MilestoneFactory(workplan=wp, status="pending")
        # Task with inactive milestone AND no workplan — should fail on guard
        task = make_task("draft", workplan=wp, milestone=ms)
        with pytest.raises(GuardViolation):
            perform_transition(task, "todo")


# ---------------------------------------------------------------------------
# Specific guards
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGuardHasWorkplan:
    """guard_has_workplan: entry guard for 'todo'."""

    def test_submit_without_workplan_blocked(self):
        from tasks.exceptions import GuardViolation
        task = make_task("draft", workplan=None)
        with pytest.raises(GuardViolation, match="workplan"):
            perform_transition(task, "todo")

    def test_submit_with_workplan_succeeds(self):
        from tests.factories import WorkplanFactory
        wp = WorkplanFactory()
        task = make_task("draft", workplan=wp)
        perform_transition(task, "todo")
        assert task.status == "todo"

    def test_recover_to_todo_without_workplan_blocked(self):
        from tasks.exceptions import GuardViolation
        task = make_task("needs_attention", workplan=None)
        with pytest.raises(GuardViolation, match="workplan"):
            perform_transition(task, "todo")

    def test_unblock_to_todo_without_workplan_blocked(self):
        from tasks.exceptions import GuardViolation
        task = make_task("blocked", workplan=None)
        with pytest.raises(GuardViolation, match="workplan"):
            perform_transition(task, "todo")

    def test_undefer_to_todo_without_workplan_blocked(self):
        from tasks.exceptions import GuardViolation
        task = make_task("deferred", workplan=None)
        with pytest.raises(GuardViolation, match="workplan"):
            perform_transition(task, "todo")


@pytest.mark.django_db
class TestGuardMilestoneActive:
    """guard_milestone_active: exit guard for 'draft'."""

    def test_submit_with_inactive_milestone_blocked(self):
        from tasks.exceptions import GuardViolation
        from tests.factories import MilestoneFactory, WorkplanFactory
        wp = WorkplanFactory()
        ms = MilestoneFactory(workplan=wp, status="pending")
        task = make_task("draft", workplan=wp, milestone=ms)
        with pytest.raises(GuardViolation, match="milestone"):
            perform_transition(task, "todo")

    def test_submit_with_active_milestone_succeeds(self):
        from tests.factories import MilestoneFactory, WorkplanFactory
        wp = WorkplanFactory()
        ms = MilestoneFactory(workplan=wp, status="active")
        task = make_task("draft", workplan=wp, milestone=ms)
        perform_transition(task, "todo")
        assert task.status == "todo"

    def test_submit_with_no_milestone_succeeds(self):
        from tests.factories import WorkplanFactory
        wp = WorkplanFactory()
        task = make_task("draft", workplan=wp, milestone=None, project=wp.project)
        perform_transition(task, "todo")
        assert task.status == "todo"

    def test_cancel_from_draft_with_inactive_milestone_blocked(self):
        """Exit guard fires on ANY transition from draft, not just submit."""
        from tasks.exceptions import GuardViolation
        from tests.factories import MilestoneFactory, WorkplanFactory
        wp = WorkplanFactory()
        ms = MilestoneFactory(workplan=wp, status="pending")
        task = make_task("draft", workplan=wp, milestone=ms)
        with pytest.raises(GuardViolation, match="milestone"):
            perform_transition(task, "cancelled")
