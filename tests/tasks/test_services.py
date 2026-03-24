"""
Unit tests for tasks/services.py — dependency resolution logic and claim_task().
"""
import threading

import pytest

from events.models import TaskEvent
from links.models import Link
from tasks.services import ClaimError, claim_task, get_tasks_with_unresolved_deps, resolve_dependencies
from tests.factories import AgentFactory, TaskFactory, MilestoneFactory, WorkplanFactory


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
        assert task.claimed_by == agent.id
        assert task.claimed_at is not None
        assert task.claim_expires_at is not None
        assert task.claim_expires_at > task.claimed_at


@pytest.mark.django_db
class TestClaimTaskErrors:
    def test_claim_task_tag_mismatch_raises(self, db):
        """ClaimError raised when agent tags do not satisfy task.requires."""
        agent = AgentFactory(tags=["other"])
        task = TaskFactory(status="todo", requires=["executor"])
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
        task = TaskFactory(status="todo", assigned_to=other.id)
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
