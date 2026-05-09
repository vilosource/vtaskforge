"""
Unit tests for tasks/services.py — dependency resolution logic and claim_task().
"""
import threading

import pytest

from events.models import TaskEvent
from links.models import Link
from tasks.models import Task
from tasks.services import (
    ClaimError,
    claim_task,
    find_claimable_tasks,
    get_available_actions,
    get_board_summary,
    get_task_context,
    get_tasks_with_unresolved_deps,
    resolve_dependencies,
)
from tasks.state_machine import VALID_TRANSITIONS
from tests.factories import AgentFactory, NoteFactory, ReviewFactory, TaskEventFactory, TaskFactory, MilestoneFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_dep_link(source_task, target_task):
    """Create a depends_on link from source_task to target_task."""
    return Link.objects.create(
        source_type="task",
        source_id=source_task.id,
        target_type="task",
        target_id=target_task.id,
        link_type="depends_on",
    )


# ---------------------------------------------------------------------------
# resolve_dependencies tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestResolveDependencies:
    def test_resolve_deps_no_deps_returns_resolved(self, db):
        """Task with no depends_on links is always resolved."""
        task = TaskFactory(status="todo")
        result = resolve_dependencies(task.id)

        assert result["resolved"] is True
        assert result["dependencies"] == []
        assert result["unresolved"] == []

    def test_resolve_deps_all_done_returns_resolved(self, db):
        """Task whose all dependency targets are done is resolved."""
        dep1 = TaskFactory(status="done")
        dep2 = TaskFactory(status="done")
        task = TaskFactory(status="todo")
        make_dep_link(task, dep1)
        make_dep_link(task, dep2)

        result = resolve_dependencies(task.id)

        assert result["resolved"] is True
        assert len(result["dependencies"]) == 2
        assert result["unresolved"] == []

    def test_resolve_deps_some_not_done_returns_unresolved(self, db):
        """Task with at least one non-done dependency is unresolved."""
        dep_done = TaskFactory(status="done")
        dep_todo = TaskFactory(status="todo")
        task = TaskFactory(status="todo")
        make_dep_link(task, dep_done)
        make_dep_link(task, dep_todo)

        result = resolve_dependencies(task.id)

        assert result["resolved"] is False
        assert len(result["dependencies"]) == 2
        assert len(result["unresolved"]) == 1
        assert result["unresolved"][0]["id"] == dep_todo.id
        assert result["unresolved"][0]["status"] == "todo"

    def test_resolve_deps_nonexistent_target_returns_unresolved_false_only_for_known(self, db):
        """Dangling link (target task not in DB) is skipped — does not block resolution."""
        task = TaskFactory(status="todo")
        # Create a link pointing to a nonexistent task ID
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id="nonexistent-task-id",
            link_type="depends_on",
        )

        result = resolve_dependencies(task.id)

        # Dangling link is skipped, so task is resolved (no known unresolved deps)
        assert result["resolved"] is True
        assert result["dependencies"] == []
        assert result["unresolved"] == []

    def test_resolve_deps_result_contains_id_title_status(self, db):
        """Each dependency entry contains id, title, and status fields."""
        dep = TaskFactory(title="Dep Task", status="doing")
        task = TaskFactory(status="todo")
        make_dep_link(task, dep)

        result = resolve_dependencies(task.id)

        assert len(result["dependencies"]) == 1
        dep_info = result["dependencies"][0]
        assert dep_info["id"] == dep.id
        assert dep_info["title"] == "Dep Task"
        assert dep_info["status"] == "doing"


# ---------------------------------------------------------------------------
# get_tasks_with_unresolved_deps tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetTasksWithUnresolvedDeps:
    def test_filters_correctly(self, db):
        """Returns only task IDs with unresolved dependencies."""
        dep_done = TaskFactory(status="done")
        dep_todo = TaskFactory(status="todo")
        task_met = TaskFactory(status="todo")       # all deps done
        task_unmet = TaskFactory(status="todo")     # has unmet dep
        task_no_dep = TaskFactory(status="todo")    # no deps at all

        make_dep_link(task_met, dep_done)
        make_dep_link(task_unmet, dep_todo)

        task_ids = [task_met.id, task_unmet.id, task_no_dep.id]
        result = get_tasks_with_unresolved_deps(task_ids)

        assert task_unmet.id in result
        assert task_met.id not in result
        assert task_no_dep.id not in result

    def test_empty_input_returns_empty_set(self, db):
        """Empty input list returns empty set without error."""
        result = get_tasks_with_unresolved_deps([])
        assert result == set()

    def test_returns_set_type(self, db):
        """Return type is a set."""
        task = TaskFactory(status="todo")
        result = get_tasks_with_unresolved_deps([task.id])
        assert isinstance(result, set)

    def test_task_not_in_input_not_returned(self, db):
        """Only IDs from the input list can appear in the result."""
        dep = TaskFactory(status="todo")
        task_in_list = TaskFactory(status="todo")
        task_not_in_list = TaskFactory(status="todo")
        make_dep_link(task_in_list, dep)
        make_dep_link(task_not_in_list, dep)

        result = get_tasks_with_unresolved_deps([task_in_list.id])

        assert task_in_list.id in result
        assert task_not_in_list.id not in result

    def test_dangling_links_do_not_make_task_unresolved(self, db):
        """Tasks whose only deps are dangling (nonexistent targets) are not unresolved."""
        task = TaskFactory(status="todo")
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id="nonexistent-id",
            link_type="depends_on",
        )

        result = get_tasks_with_unresolved_deps([task.id])

        assert task.id not in result


# ---------------------------------------------------------------------------
# claim_task() service function tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimTaskSuccess:
    def test_claim_task_success(self, db):
        """Basic claim: task transitions to doing and is returned."""
        agent = AgentFactory(tags=[])
        task = TaskFactory(status="todo")
        claimed = claim_task(task.id, agent.id, [])
        assert claimed.status == "doing"

    def test_claim_task_sets_claim_fields(self, db):
        """claim_task sets claimed_by, claimed_at, and claim_expires_at."""
        agent = AgentFactory(tags=[])
        task = TaskFactory(status="todo")
        claimed = claim_task(task.id, agent.id, [])
        task.refresh_from_db()
        assert task.claimed_by == agent.user
        assert task.claimed_at is not None
        assert task.claim_expires_at is not None
        assert task.claim_expires_at > task.claimed_at


@pytest.mark.django_db
class TestClaimTaskErrors:
    def test_claim_task_tag_mismatch_raises(self, db):
        """ClaimError raised when agent tags do not satisfy task.requires."""
        agent = AgentFactory(tags=["other"])
        task = TaskFactory(status="todo", required_tags=["executor"])
        with pytest.raises(ClaimError) as exc_info:
            claim_task(task.id, agent.id, ["other"])
        assert exc_info.value.code == "tag_mismatch"
        assert exc_info.value.status_code == 422

    def test_claim_task_wrong_status_raises(self, db):
        """ClaimError raised when task is not in todo status."""
        agent = AgentFactory(tags=[])
        task = TaskFactory(status="doing")
        with pytest.raises(ClaimError) as exc_info:
            claim_task(task.id, agent.id, [])
        assert exc_info.value.code == "ALREADY_CLAIMED"
        assert exc_info.value.status_code == 409

    def test_claim_task_assigned_to_other_raises(self, db):
        """ClaimError raised when task is assigned to a different agent."""
        agent = AgentFactory(tags=[])
        other = AgentFactory(tags=[])
        task = TaskFactory(status="todo", assigned_to=other.user)
        with pytest.raises(ClaimError) as exc_info:
            claim_task(task.id, agent.id, [])
        assert exc_info.value.code == "FORBIDDEN"
        assert exc_info.value.status_code == 403

    def test_claim_task_unresolved_deps_raises(self, db):
        """ClaimError raised when task has unresolved dependencies."""
        agent = AgentFactory(tags=[])
        dep = TaskFactory(status="todo")
        task = TaskFactory(status="todo")
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep.id,
            link_type="depends_on",
        )
        with pytest.raises(ClaimError) as exc_info:
            claim_task(task.id, agent.id, [])
        assert exc_info.value.code == "deps_unmet"
        assert exc_info.value.status_code == 422


@pytest.mark.django_db
class TestClaimTaskEvent:
    def test_claim_task_creates_event(self, db):
        """claim_task creates a 'claimed' TaskEvent."""
        agent = AgentFactory(tags=[])
        task = TaskFactory(status="todo")
        claim_task(task.id, agent.id, [])
        assert TaskEvent.objects.filter(task=task, event_type="claimed").exists()


@pytest.mark.django_db(transaction=True)
class TestClaimTaskAtomic:
    def test_claim_task_atomic(self):
        """Concurrent calls to claim_task — exactly one succeeds, one raises ClaimError."""
        agent_a = AgentFactory(tags=[])
        agent_b = AgentFactory(tags=[])
        task = TaskFactory(status="todo")
        results = []

        def do_claim(agent_id):
            try:
                claim_task(task.id, agent_id, [])
                results.append("ok")
            except ClaimError:
                results.append("error")

        t1 = threading.Thread(target=do_claim, args=(agent_a.id,))
        t2 = threading.Thread(target=do_claim, args=(agent_b.id,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(results) == ["error", "ok"]


# ---------------------------------------------------------------------------
# find_claimable_tasks() service function tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFindClaimableTasks:
    def test_find_claimable_basic(self, db):
        """Returns todo tasks and excludes non-todo tasks."""
        task_todo_a = TaskFactory(status="todo", title="Todo A")
        task_todo_b = TaskFactory(status="todo", title="Todo B")
        TaskFactory(status="doing", title="Doing")
        TaskFactory(status="done", title="Done")
        TaskFactory(status="draft", title="Draft")

        result = list(find_claimable_tasks())
        result_ids = [t.id for t in result]

        assert task_todo_a.id in result_ids
        assert task_todo_b.id in result_ids
        assert len(result_ids) == 2

    def test_find_claimable_excludes_tasks_with_unmet_deps(self, db):
        """Tasks with unresolved dependencies are excluded from results."""
        dep_unmet = TaskFactory(status="todo", title="Unmet Dep")
        dep_met = TaskFactory(status="done", title="Met Dep")
        task_blocked = TaskFactory(status="todo", title="Blocked by unmet dep")
        task_ready = TaskFactory(status="todo", title="Ready, dep is done")
        task_no_dep = TaskFactory(status="todo", title="No dep")

        Link.objects.create(
            source_type="task",
            source_id=task_blocked.id,
            target_type="task",
            target_id=dep_unmet.id,
            link_type="depends_on",
        )
        Link.objects.create(
            source_type="task",
            source_id=task_ready.id,
            target_type="task",
            target_id=dep_met.id,
            link_type="depends_on",
        )

        result_ids = [t.id for t in find_claimable_tasks()]

        assert task_blocked.id not in result_ids
        assert task_ready.id in result_ids
        assert task_no_dep.id in result_ids

    def test_find_claimable_filters_by_tags(self, db):
        """task.requires must be a subset of provided tags; tasks with unmatched requires excluded."""
        task_no_requires = TaskFactory(status="todo", required_tags=[], title="No requires")
        task_executor = TaskFactory(status="todo", required_tags=["executor"], title="Needs executor")
        task_opus = TaskFactory(status="todo", required_tags=["opus"], title="Needs opus")
        task_both = TaskFactory(status="todo", required_tags=["executor", "opus"], title="Needs both")

        # Tags: only executor — should see no-requires and executor tasks
        result_ids = [t.id for t in find_claimable_tasks(tags=["executor"])]
        assert task_no_requires.id in result_ids
        assert task_executor.id in result_ids
        assert task_opus.id not in result_ids
        assert task_both.id not in result_ids

        # Tags: executor and opus — should see all
        result_ids = [t.id for t in find_claimable_tasks(tags=["executor", "opus"])]
        assert task_no_requires.id in result_ids
        assert task_executor.id in result_ids
        assert task_opus.id in result_ids
        assert task_both.id in result_ids

        # No tags — tag filtering skipped, all todo tasks included
        result_ids = [t.id for t in find_claimable_tasks(tags=None)]
        assert task_executor.id in result_ids
        assert task_opus.id in result_ids

    def test_find_claimable_filters_by_assignment(self, db):
        """Excludes tasks assigned to other agents; includes unassigned and self-assigned."""
        from tests.factories import AgentFactory

        agent = AgentFactory(tags=[])
        other = AgentFactory(tags=[])

        task_unassigned = TaskFactory(status="todo", assigned_to=None, title="Unassigned")
        task_mine = TaskFactory(status="todo", assigned_to=agent.user, title="Mine")
        task_other = TaskFactory(status="todo", assigned_to=other.user, title="Other agent's")

        result_ids = [t.id for t in find_claimable_tasks(agent_id=agent.id)]

        assert task_unassigned.id in result_ids
        assert task_mine.id in result_ids
        assert task_other.id not in result_ids

        # Without agent_id — all tasks included regardless of assignment
        result_ids_no_agent = [t.id for t in find_claimable_tasks()]
        assert task_other.id in result_ids_no_agent

    def test_find_claimable_filters_by_project(self, db):
        """Only tasks in the specified project are returned when project_id is given."""
        from tests.factories import ProjectFactory

        project_a = ProjectFactory()
        project_b = ProjectFactory()

        task_a = TaskFactory(status="todo", project=project_a, milestone=None, workplan=None, title="Task A")
        task_b = TaskFactory(status="todo", project=project_b, milestone=None, workplan=None, title="Task B")

        result_a_ids = [t.id for t in find_claimable_tasks(project_id=project_a.id)]
        assert task_a.id in result_a_ids
        assert task_b.id not in result_a_ids

        result_b_ids = [t.id for t in find_claimable_tasks(project_id=project_b.id)]
        assert task_b.id in result_b_ids
        assert task_a.id not in result_b_ids

        # No project filter — all tasks included
        result_all_ids = [t.id for t in find_claimable_tasks()]
        assert task_a.id in result_all_ids
        assert task_b.id in result_all_ids


# ---------------------------------------------------------------------------
# get_available_actions() tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAvailableActions:
    @pytest.mark.parametrize("status", list(VALID_TRANSITIONS.keys()))
    def test_get_available_actions_for_each_status(self, db, status):
        """get_available_actions returns exactly the transitions from VALID_TRANSITIONS."""
        task = TaskFactory(status=status)
        actions = get_available_actions(task)
        assert actions == VALID_TRANSITIONS[status]

    def test_get_available_actions_terminal_statuses_empty(self, db):
        """Terminal statuses (done, cancelled) return an empty list."""
        done_task = TaskFactory(status="done")
        cancelled_task = TaskFactory(status="cancelled")
        assert get_available_actions(done_task) == []
        assert get_available_actions(cancelled_task) == []


# ---------------------------------------------------------------------------
# get_task_context() tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetTaskContext:
    def test_get_task_context_includes_all_fields(self, db):
        """get_task_context returns a dict with all required top-level keys and task fields."""
        task = TaskFactory(status="todo", spec="spec content here")
        context = get_task_context(task.id)

        # Top-level keys
        assert "task" in context
        assert "spec" in context
        assert "dependencies" in context
        assert "reviews" in context
        assert "events" in context
        assert "notes" in context
        assert "actions" in context

        # Task fields
        t = context["task"]
        assert t["id"] == task.id
        assert t["title"] == task.title
        assert t["status"] == task.status
        assert t["project_id"] == task.project_id

        # Spec
        assert context["spec"] == "spec content here"

        # Actions should be a list consistent with state machine
        assert context["actions"] == VALID_TRANSITIONS["todo"]

    def test_get_task_context_includes_reviews(self, db):
        """get_task_context includes related reviews."""
        task = TaskFactory(status="todo")
        review = ReviewFactory(task=task, decision="approved", reason="Looks good")

        context = get_task_context(task.id)

        assert len(context["reviews"]) == 1
        r = context["reviews"][0]
        assert r["id"] == review.id
        assert r["decision"] == "approved"
        assert r["reason"] == "Looks good"
        assert r["reviewer_id"] == review.reviewer_id

    def test_get_task_context_includes_events(self, db):
        """get_task_context includes related task events."""
        task = TaskFactory(status="todo")
        event = TaskEventFactory(task=task, event_type="status_changed")

        context = get_task_context(task.id)

        event_ids = [e["id"] for e in context["events"]]
        assert event.id in event_ids

    def test_get_task_context_includes_notes(self, db):
        """get_task_context includes related notes."""
        task = TaskFactory(status="todo")
        note = NoteFactory(task=task, text="important note")

        context = get_task_context(task.id)

        assert len(context["notes"]) == 1
        assert context["notes"][0]["id"] == note.id
        assert context["notes"][0]["text"] == "important note"

    def test_get_task_context_dependency_status(self, db):
        """get_task_context includes dependency resolution status."""
        dep = TaskFactory(status="todo")
        task = TaskFactory(status="todo")
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep.id,
            link_type="depends_on",
        )

        context = get_task_context(task.id)

        deps = context["dependencies"]
        assert deps["resolved"] is False
        assert len(deps["unresolved"]) == 1
        assert deps["unresolved"][0]["id"] == dep.id

    def test_get_task_context_raises_for_missing_task(self, db):
        """get_task_context raises Task.DoesNotExist for unknown task_id."""
        with pytest.raises(Task.DoesNotExist):
            get_task_context("nonexistent-id")


# ---------------------------------------------------------------------------
# get_board_summary() tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetBoardSummary:
    def test_get_board_summary_counts(self, db):
        """get_board_summary returns correct counts by status."""
        TaskFactory(status="todo")
        TaskFactory(status="todo")
        TaskFactory(status="doing")
        TaskFactory(status="done")

        summary = get_board_summary()

        assert summary["counts"].get("todo", 0) >= 2
        assert summary["counts"].get("doing", 0) >= 1
        assert summary["counts"].get("done", 0) >= 1

    def test_get_board_summary_counts_filtered_by_project(self, db):
        """get_board_summary filters counts by project_id."""
        from tests.factories import ProjectFactory

        project_a = ProjectFactory()
        project_b = ProjectFactory()

        TaskFactory(status="todo", project=project_a, milestone=None, workplan=None)
        TaskFactory(status="todo", project=project_a, milestone=None, workplan=None)
        TaskFactory(status="doing", project=project_b, milestone=None, workplan=None)

        summary_a = get_board_summary(project_id=project_a.id)
        assert summary_a["counts"].get("todo", 0) == 2
        assert summary_a["counts"].get("doing", 0) == 0

        summary_b = get_board_summary(project_id=project_b.id)
        assert summary_b["counts"].get("todo", 0) == 0
        assert summary_b["counts"].get("doing", 0) == 1

    def test_get_board_summary_attention_items(self, db):
        """get_board_summary includes blocked and needs_attention tasks."""
        blocked = TaskFactory(status="blocked", title="Blocked Task")
        attention = TaskFactory(status="needs_attention", title="Attention Task")
        TaskFactory(status="todo", title="Regular Task")

        summary = get_board_summary()

        attention_ids = [item["id"] for item in summary["attention_items"]]
        assert blocked.id in attention_ids
        assert attention.id in attention_ids

        # Regular todo tasks must not be in attention_items
        regular_ids = [item["id"] for item in summary["attention_items"] if item["status"] == "todo"]
        assert len(regular_ids) == 0

    def test_get_board_summary_pending_reviews(self, db):
        """get_board_summary includes tasks in pending review statuses."""
        pending_start = TaskFactory(status="pending_start_review", title="Pending Start")
        pending_completion = TaskFactory(status="pending_completion_review", title="Pending Completion")
        TaskFactory(status="todo", title="Not pending")

        summary = get_board_summary()

        pending_ids = [item["id"] for item in summary["pending_reviews"]]
        assert pending_start.id in pending_ids
        assert pending_completion.id in pending_ids

    def test_get_board_summary_active_agents(self, db):
        """get_board_summary returns active agents from tasks in doing status."""
        from django.utils import timezone
        from datetime import timedelta

        agent = AgentFactory(name="agent-xyz")
        doing_task = TaskFactory(
            status="doing",
            claimed_by=agent.user,
            claimed_at=timezone.now(),
            claim_expires_at=timezone.now() + timedelta(minutes=30),
        )
        TaskFactory(status="doing", claimed_by=None)  # doing but not claimed
        TaskFactory(status="todo")

        summary = get_board_summary()

        agent_task_ids = [a["id"] for a in summary["active_agents"]]
        assert doing_task.id in agent_task_ids

        # Verify agent info is included (claimed_by is returned as User PK from .values())
        agent_entry = next(a for a in summary["active_agents"] if a["id"] == doing_task.id)
        assert agent_entry["claimed_by"] == agent.user.pk
