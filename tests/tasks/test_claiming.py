"""
Tests for atomic claim logic (task 1.12).

Covers:
- VALIDATION_ERROR (400/422): missing agent_id, tag mismatch
- ALREADY_CLAIMED (409): task not in todo status
- FORBIDDEN (403): task assigned to another agent
- DEPENDENCY_UNMET (422): depends_on links with non-done deps
- Concurrent claim race: one succeeds, other gets 409
- Claimable endpoint: tag filtering, assignment filtering, dep filtering
- DB tag lookup: agent tags resolved from Agent model when not in request
"""
import threading

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from links.models import Link
from tests.factories import AgentFactory, MilestoneFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def milestone(db, workplan):
    return MilestoneFactory(name="Test Phase", workplan=workplan)


@pytest.fixture
def agent1(db):
    return AgentFactory(name="Agent 1", tags=[])


@pytest.fixture
def agent_other(db):
    return AgentFactory(name="Agent Other", tags=[])


def make_task(milestone, workplan, task_status="todo", **kwargs):
    kwargs.setdefault("title", "Test Task")
    return TaskFactory(
        milestone=milestone,
        workplan=workplan,
        status=task_status,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Basic claim: success path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimSuccess:
    def test_claim_todo_returns_200(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_transitions_to_doing(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["status"] == "doing"

    def test_claim_sets_claimed_by(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["claimed_by"] == agent1.id

    def test_claim_sets_claim_expires_at(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["claim_expires_at"] is not None

    def test_claim_persists_to_db(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan)
        api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        task.refresh_from_db()
        assert task.status == "doing"
        assert task.claimed_by == agent1.user
        assert task.claimed_at is not None
        assert task.claim_expires_at is not None


# ---------------------------------------------------------------------------
# Rework claim: changes_requested → doing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimRework:
    def test_claim_changes_requested_returns_200(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "changes_requested")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_changes_requested_transitions_to_doing(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "changes_requested")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["status"] == "doing"

    def test_claim_changes_requested_sets_claimed_by(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "changes_requested")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["claimed_by"] == agent1.id

    def test_claim_changes_requested_different_agent(self, api_client, milestone, workplan, agent1):
        """Any agent can claim a changes_requested task, not just the original executor."""
        agent2 = AgentFactory(name="Agent Two", tags=["executor"])
        original_agent = AgentFactory(name="original-agent")
        task = make_task(milestone, workplan, "changes_requested", claimed_by=original_agent.user)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent2.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["claimed_by"] == agent2.id


# ---------------------------------------------------------------------------
# VALIDATION_ERROR: missing agent_id (400)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimMissingAgentId:
    def test_missing_agent_id_returns_400(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan)
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_agent_id_error_code(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan)
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {}, format="json")
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_agent_id_does_not_change_status(self, api_client, milestone, workplan):
        task = make_task(milestone, workplan)
        api_client.post(f"/v1/tasks/{task.id}/claim/", {}, format="json")
        task.refresh_from_db()
        assert task.status == "todo"


# ---------------------------------------------------------------------------
# ALREADY_CLAIMED (409): task not in todo status
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimAlreadyClaimed:
    def test_claim_doing_returns_409(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_claim_doing_error_code(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["error"]["code"] == "ALREADY_CLAIMED"

    def test_claim_doing_includes_current_status(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "doing")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["error"]["details"]["current_status"] == "doing"

    def test_claim_done_returns_409(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "done")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_claim_draft_returns_409(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "draft")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_claim_blocked_returns_409(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, "blocked")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT


# ---------------------------------------------------------------------------
# NOT_FOUND (404): task does not exist
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimNotFound:
    def test_claim_nonexistent_task_returns_404(self, api_client, agent1):
        response = api_client.post(
            "/v1/tasks/nonexistent-id/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_claim_nonexistent_task_error_code(self, api_client, agent1):
        response = api_client.post(
            "/v1/tasks/nonexistent-id/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# FORBIDDEN (403): task assigned to a different agent
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimForbidden:
    def test_claim_assigned_to_other_returns_403(
        self, api_client, milestone, workplan, agent1, agent_other
    ):
        task = make_task(milestone, workplan, assigned_to=agent_other.user)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_claim_assigned_to_other_error_code(
        self, api_client, milestone, workplan, agent1, agent_other
    ):
        task = make_task(milestone, workplan, assigned_to=agent_other.user)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["error"]["code"] == "FORBIDDEN"

    def test_claim_assigned_to_self_succeeds(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, assigned_to=agent1.user)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_unassigned_task_succeeds(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# VALIDATION_ERROR (422): tag mismatch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimTagMismatch:
    def test_missing_required_tag_returns_422(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, required_tags=["executor", "opus"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent1.id, "tags": ["executor"]},
            format="json",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_tag_error_code(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, required_tags=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent1.id, "tags": []},
            format="json",
        )
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_required_tag_includes_details(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, required_tags=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent1.id, "tags": ["other"]},
            format="json",
        )
        details = response.data["error"]["details"]
        assert "required_tags" in details
        assert "agent_tags" in details

    def test_exact_tag_match_succeeds(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, required_tags=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent1.id, "tags": ["executor"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_superset_tags_succeed(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, required_tags=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent1.id, "tags": ["executor", "opus", "extra"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_empty_requires_any_agent_can_claim(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, required_tags=[])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent1.id, "tags": []},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_no_tags_provided_empty_requires_succeeds(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan, required_tags=[])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent1.id},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# DEPENDENCY_UNMET (422): depends_on links
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimDependencyUnmet:
    def test_unmet_dependency_returns_422(self, api_client, milestone, workplan, agent1):
        dep_task = make_task(milestone, workplan, "todo")
        task = make_task(milestone, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_unmet_dependency_error_code(self, api_client, milestone, workplan, agent1):
        dep_task = make_task(milestone, workplan, "todo")
        task = make_task(milestone, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.data["error"]["code"] == "DEPENDENCY_UNMET"

    def test_unmet_dependency_includes_details(self, api_client, milestone, workplan, agent1):
        dep_task = make_task(milestone, workplan, "doing")
        task = make_task(milestone, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        details = response.data["error"]["details"]
        assert details["dependency_id"] == dep_task.id
        assert details["dependency_status"] == "doing"

    def test_done_dependency_allows_claim(self, api_client, milestone, workplan, agent1):
        dep_task = make_task(milestone, workplan, "done")
        task = make_task(milestone, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_nonexistent_target_dependency_skipped(self, api_client, milestone, workplan, agent1):
        task = make_task(milestone, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="external",
            target_id="external-ref-123",
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        # External dependency (target task doesn't exist) is skipped
        assert response.status_code == status.HTTP_200_OK

    def test_multiple_deps_all_done_allows_claim(self, api_client, milestone, workplan, agent1):
        dep1 = make_task(milestone, workplan, "done")
        dep2 = make_task(milestone, workplan, "done")
        task = make_task(milestone, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep1.id,
            link_type="depends_on",
        )
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep2.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_one_unmet_dep_among_many_blocks_claim(self, api_client, milestone, workplan, agent1):
        dep1 = make_task(milestone, workplan, "done")
        dep2 = make_task(milestone, workplan, "todo")
        task = make_task(milestone, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep1.id,
            link_type="depends_on",
        )
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep2.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": agent1.id}, format="json"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.data["error"]["code"] == "DEPENDENCY_UNMET"


# ---------------------------------------------------------------------------
# Concurrent claim race
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestConcurrentClaim:
    def _make_token_key(self):
        """Create a shared auth token for use in threads."""
        user = User.objects.create_user(username="concurrent-test-user")
        token = Token.objects.create(user=user)
        return token.key

    def _make_agents(self):
        """Create two agents for concurrent testing."""
        agent_a = AgentFactory(name="Agent A", tags=[])
        agent_b = AgentFactory(name="Agent B", tags=[])
        return agent_a.id, agent_b.id

    def test_concurrent_claim_one_wins_one_gets_409(self, milestone, workplan):
        """Two agents race to claim the same task; exactly one should win."""
        task = make_task(milestone, workplan)
        token_key = self._make_token_key()
        agent_a_id, agent_b_id = self._make_agents()
        results = []

        def do_claim(agent_id):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Token {token_key}")
            resp = client.post(
                f"/v1/tasks/{task.id}/claim/",
                {"agent_id": agent_id},
                format="json",
            )
            results.append(resp.status_code)

        t1 = threading.Thread(target=do_claim, args=(agent_a_id,))
        t2 = threading.Thread(target=do_claim, args=(agent_b_id,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(results) == [200, 409]

    def test_concurrent_claim_task_ends_in_doing(self, milestone, workplan):
        """After concurrent claims, task should be in 'doing' state."""
        task = make_task(milestone, workplan)
        token_key = self._make_token_key()
        agent_a_id, agent_b_id = self._make_agents()

        def do_claim(agent_id):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Token {token_key}")
            client.post(
                f"/v1/tasks/{task.id}/claim/",
                {"agent_id": agent_id},
                format="json",
            )

        t1 = threading.Thread(target=do_claim, args=(agent_a_id,))
        t2 = threading.Thread(target=do_claim, args=(agent_b_id,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        task.refresh_from_db()
        assert task.status == "doing"


# ---------------------------------------------------------------------------
# Claimable endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimableEndpoint:
    def test_claimable_returns_todo_tasks(self, api_client, milestone, workplan):
        make_task(milestone, workplan, "todo", title="Task A")
        make_task(milestone, workplan, "todo", title="Task B")
        make_task(milestone, workplan, "doing", title="Task C")
        response = api_client.get("/v1/tasks/claimable/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_claimable_excludes_non_todo(self, api_client, milestone, workplan):
        make_task(milestone, workplan, "draft")
        make_task(milestone, workplan, "doing")
        make_task(milestone, workplan, "done")
        make_task(milestone, workplan, "blocked")
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data["results"]) == 0

    def test_claimable_tag_filter_includes_matching(self, api_client, milestone, workplan):
        make_task(milestone, workplan, required_tags=["executor"])
        make_task(milestone, workplan, required_tags=[])
        response = api_client.get("/v1/tasks/claimable/?tags=executor")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_claimable_tag_filter_excludes_non_matching(self, api_client, milestone, workplan):
        make_task(milestone, workplan, required_tags=["opus"])
        make_task(milestone, workplan, required_tags=["executor"])
        response = api_client.get("/v1/tasks/claimable/?tags=executor")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["required_tags"] == ["executor"]

    def test_claimable_no_tags_returns_all_todo(self, api_client, milestone, workplan):
        make_task(milestone, workplan, required_tags=["executor"])
        make_task(milestone, workplan, required_tags=[])
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data["results"]) == 2

    def test_claimable_excludes_tasks_with_unmet_deps(self, api_client, milestone, workplan):
        dep_task = make_task(milestone, workplan, "todo", title="Dep")
        task = make_task(milestone, workplan, title="Dependent")
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.get("/v1/tasks/claimable/")
        ids = [t["id"] for t in response.data["results"]]
        assert task.id not in ids

    def test_claimable_includes_tasks_with_met_deps(self, api_client, milestone, workplan):
        dep_task = make_task(milestone, workplan, "done", title="Dep")
        task = make_task(milestone, workplan, title="Dependent")
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.get("/v1/tasks/claimable/")
        ids = [t["id"] for t in response.data["results"]]
        assert task.id in ids

    def test_claimable_agent_id_excludes_other_assigned(
        self, api_client, milestone, workplan, agent1, agent_other
    ):
        make_task(milestone, workplan, assigned_to=agent_other.user, title="Other's task")
        make_task(milestone, workplan, assigned_to=None, title="Unassigned")
        response = api_client.get(f"/v1/tasks/claimable/?agent_id={agent1.id}")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "Unassigned"

    def test_claimable_agent_id_includes_own_assigned(
        self, api_client, milestone, workplan, agent1
    ):
        make_task(milestone, workplan, assigned_to=agent1.user, title="My task")
        make_task(milestone, workplan, assigned_to=None, title="Unassigned")
        response = api_client.get(f"/v1/tasks/claimable/?agent_id={agent1.id}")
        assert len(response.data["results"]) == 2

    def test_claimable_no_agent_id_shows_all_todo(self, api_client, milestone, workplan, agent_other):
        make_task(milestone, workplan, assigned_to=agent_other.user)
        make_task(milestone, workplan, assigned_to=None)
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data["results"]) == 2

    def test_claimable_combined_tags_and_deps(self, api_client, milestone, workplan):
        dep = make_task(milestone, workplan, "done", title="Dep")
        task_with_dep = make_task(milestone, workplan, required_tags=["executor"], title="With dep")
        Link.objects.create(
            source_type="task",
            source_id=task_with_dep.id,
            target_type="task",
            target_id=dep.id,
            link_type="depends_on",
        )
        task_no_dep = make_task(milestone, workplan, required_tags=["executor"], title="No dep")
        response = api_client.get("/v1/tasks/claimable/?tags=executor")
        ids = [t["id"] for t in response.data["results"]]
        assert task_with_dep.id in ids
        assert task_no_dep.id in ids

    def test_claimable_excludes_pending_milestone_tasks(self, api_client, workplan):
        pending_ms = MilestoneFactory(name="Pending", workplan=workplan, status="pending")
        active_ms = MilestoneFactory(name="Active", workplan=workplan, status="active")
        make_task(pending_ms, workplan, "todo", title="Pending MS task")
        make_task(active_ms, workplan, "todo", title="Active MS task")
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "Active MS task"

    def test_claimable_excludes_completed_milestone_tasks(self, api_client, workplan):
        completed_ms = MilestoneFactory(name="Completed", workplan=workplan, status="completed")
        make_task(completed_ms, workplan, "todo", title="Completed MS task")
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data["results"]) == 0

    def test_claimable_includes_tasks_without_milestone(self, api_client, workplan):
        """Backlog tasks (no milestone) are always claimable."""
        TaskFactory(title="Backlog", workplan=None, milestone=None, project=workplan.project, status="todo")
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["title"] == "Backlog"


# ---------------------------------------------------------------------------
# DB tag lookup: claim uses agent.tags from DB when not in request body
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimDBTagLookup:
    def test_claim_uses_db_tags_when_no_body_tags(self, api_client, milestone, workplan):
        """When no tags in request body, agent's DB tags are used for matching."""
        agent = AgentFactory(tags=["executor"])
        task = make_task(milestone, workplan, required_tags=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent.id},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_db_tags_mismatch_returns_422(self, api_client, milestone, workplan):
        """When agent DB tags don't match task requires, 422 is returned."""
        agent = AgentFactory(tags=["other"])
        task = make_task(milestone, workplan, required_tags=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent.id},
            format="json",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_claim_body_tags_override_db_tags(self, api_client, milestone, workplan):
        """When tags are provided in request body, they override agent's DB tags."""
        agent = AgentFactory(tags=["other"])
        task = make_task(milestone, workplan, required_tags=["executor"])
        # Providing matching tags in the body should succeed even though DB tags don't match
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent.id, "tags": ["executor"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_body_tags_can_cause_mismatch(self, api_client, milestone, workplan):
        """Body tags that don't match task requires return 422 even if DB tags would match."""
        agent = AgentFactory(tags=["executor"])
        task = make_task(milestone, workplan, required_tags=["executor"])
        # Providing non-matching tags in the body should fail even though DB tags match
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": agent.id, "tags": ["other"]},
            format="json",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_claim_nonexistent_agent_returns_404(self, api_client, milestone, workplan):
        """Claim with a non-existent agent_id returns 404."""
        task = make_task(milestone, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "nonexistent-agent-id"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"]["code"] == "NOT_FOUND"

    def test_claim_nonexistent_agent_does_not_change_task(self, api_client, milestone, workplan):
        """Claim with a non-existent agent_id does not change task status."""
        task = make_task(milestone, workplan)
        api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "nonexistent-agent-id"},
            format="json",
        )
        task.refresh_from_db()
        assert task.status == "todo"


# ---------------------------------------------------------------------------
# Claimable endpoint with agent_id DB tag lookup
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimableDBTagLookup:
    def test_claimable_with_agent_id_uses_db_tags(self, api_client, milestone, workplan):
        """claimable?agent_id= uses agent's DB tags for filtering when no tags param."""
        agent = AgentFactory(tags=["executor"])
        make_task(milestone, workplan, required_tags=["executor"], title="Matching task")
        make_task(milestone, workplan, required_tags=["opus"], title="Non-matching task")
        response = api_client.get(f"/v1/tasks/claimable/?agent_id={agent.id}")
        assert response.status_code == status.HTTP_200_OK
        titles = [t["title"] for t in response.data["results"]]
        assert "Matching task" in titles
        assert "Non-matching task" not in titles

    def test_claimable_tags_param_overrides_db_tags(self, api_client, milestone, workplan):
        """Explicit tags param overrides DB agent tags in claimable endpoint."""
        agent = AgentFactory(tags=["executor"])
        make_task(milestone, workplan, required_tags=["opus"], title="Opus task")
        make_task(milestone, workplan, required_tags=["executor"], title="Executor task")
        # Explicit tags=opus in query param should override agent's DB tags (executor)
        response = api_client.get(f"/v1/tasks/claimable/?agent_id={agent.id}&tags=opus")
        titles = [t["title"] for t in response.data["results"]]
        assert "Opus task" in titles
        assert "Executor task" not in titles

    def test_claimable_nonexistent_agent_id_returns_all_todo(
        self, api_client, milestone, workplan
    ):
        """claimable with non-existent agent_id falls back to no tag filtering."""
        make_task(milestone, workplan, required_tags=[], title="No requires")
        make_task(milestone, workplan, required_tags=["executor"], title="Needs executor")
        response = api_client.get("/v1/tasks/claimable/?agent_id=nonexistent")
        # With empty tags from failed DB lookup, tag filter is skipped — all todo tasks returned
        assert response.status_code == status.HTTP_200_OK
        titles = [t["title"] for t in response.data["results"]]
        assert "No requires" in titles
        assert "Needs executor" in titles

