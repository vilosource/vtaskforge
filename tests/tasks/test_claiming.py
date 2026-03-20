"""
Tests for atomic claim logic (task 1.12).

Covers:
- VALIDATION_ERROR (400/422): missing agent_id, tag mismatch
- ALREADY_CLAIMED (409): task not in todo status
- FORBIDDEN (403): task assigned to another agent
- DEPENDENCY_UNMET (422): depends_on links with non-done deps
- Concurrent claim race: one succeeds, other gets 409
- Claimable endpoint: tag filtering, assignment filtering, dep filtering
"""
import threading

import pytest
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from links.models import Link
from tests.factories import PhaseFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.fixture
def phase(db, workplan):
    return PhaseFactory(name="Test Phase", workplan=workplan)


def make_task(phase, workplan, task_status="todo", **kwargs):
    kwargs.setdefault("title", "Test Task")
    return TaskFactory(
        phase=phase,
        workplan=workplan,
        status=task_status,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Basic claim: success path
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimSuccess:
    def test_claim_todo_returns_200(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_transitions_to_doing(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["status"] == "doing"

    def test_claim_sets_claimed_by(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["claimed_by"] == "agent-1"

    def test_claim_sets_claim_expires_at(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["claim_expires_at"] is not None

    def test_claim_persists_to_db(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        task.refresh_from_db()
        assert task.status == "doing"
        assert task.claimed_by == "agent-1"
        assert task.claimed_at is not None
        assert task.claim_expires_at is not None


# ---------------------------------------------------------------------------
# VALIDATION_ERROR: missing agent_id (400)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimMissingAgentId:
    def test_missing_agent_id_returns_400(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_agent_id_error_code(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        response = api_client.post(f"/v1/tasks/{task.id}/claim/", {}, format="json")
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_agent_id_does_not_change_status(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        api_client.post(f"/v1/tasks/{task.id}/claim/", {}, format="json")
        task.refresh_from_db()
        assert task.status == "todo"


# ---------------------------------------------------------------------------
# ALREADY_CLAIMED (409): task not in todo status
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimAlreadyClaimed:
    def test_claim_doing_returns_409(self, api_client, phase, workplan):
        task = make_task(phase, workplan, "doing")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_claim_doing_error_code(self, api_client, phase, workplan):
        task = make_task(phase, workplan, "doing")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["error"]["code"] == "ALREADY_CLAIMED"

    def test_claim_doing_includes_current_status(self, api_client, phase, workplan):
        task = make_task(phase, workplan, "doing")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["error"]["details"]["current_status"] == "doing"

    def test_claim_done_returns_409(self, api_client, phase, workplan):
        task = make_task(phase, workplan, "done")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_claim_draft_returns_409(self, api_client, phase, workplan):
        task = make_task(phase, workplan, "draft")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_claim_blocked_returns_409(self, api_client, phase, workplan):
        task = make_task(phase, workplan, "blocked")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_409_CONFLICT


# ---------------------------------------------------------------------------
# NOT_FOUND (404): task does not exist
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimNotFound:
    def test_claim_nonexistent_task_returns_404(self, api_client):
        response = api_client.post(
            "/v1/tasks/nonexistent-id/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_claim_nonexistent_task_error_code(self, api_client):
        response = api_client.post(
            "/v1/tasks/nonexistent-id/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# FORBIDDEN (403): task assigned to a different agent
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimForbidden:
    def test_claim_assigned_to_other_returns_403(self, api_client, phase, workplan):
        task = make_task(phase, workplan, assigned_to="agent-other")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_claim_assigned_to_other_error_code(self, api_client, phase, workplan):
        task = make_task(phase, workplan, assigned_to="agent-other")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["error"]["code"] == "FORBIDDEN"

    def test_claim_assigned_to_self_succeeds(self, api_client, phase, workplan):
        task = make_task(phase, workplan, assigned_to="agent-1")
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_claim_unassigned_task_succeeds(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# VALIDATION_ERROR (422): tag mismatch
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimTagMismatch:
    def test_missing_required_tag_returns_422(self, api_client, phase, workplan):
        task = make_task(phase, workplan, requires=["executor", "opus"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "agent-1", "tags": ["executor"]},
            format="json",
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_tag_error_code(self, api_client, phase, workplan):
        task = make_task(phase, workplan, requires=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "agent-1", "tags": []},
            format="json",
        )
        assert response.data["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_required_tag_includes_details(self, api_client, phase, workplan):
        task = make_task(phase, workplan, requires=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "agent-1", "tags": ["other"]},
            format="json",
        )
        details = response.data["error"]["details"]
        assert "requires" in details
        assert "agent_tags" in details

    def test_exact_tag_match_succeeds(self, api_client, phase, workplan):
        task = make_task(phase, workplan, requires=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "agent-1", "tags": ["executor"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_superset_tags_succeed(self, api_client, phase, workplan):
        task = make_task(phase, workplan, requires=["executor"])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "agent-1", "tags": ["executor", "opus", "extra"]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_empty_requires_any_agent_can_claim(self, api_client, phase, workplan):
        task = make_task(phase, workplan, requires=[])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "agent-1", "tags": []},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_no_tags_provided_empty_requires_succeeds(self, api_client, phase, workplan):
        task = make_task(phase, workplan, requires=[])
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/",
            {"agent_id": "agent-1"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


# ---------------------------------------------------------------------------
# DEPENDENCY_UNMET (422): depends_on links
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestClaimDependencyUnmet:
    def test_unmet_dependency_returns_422(self, api_client, phase, workplan):
        dep_task = make_task(phase, workplan, "todo")
        task = make_task(phase, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_unmet_dependency_error_code(self, api_client, phase, workplan):
        dep_task = make_task(phase, workplan, "todo")
        task = make_task(phase, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.data["error"]["code"] == "DEPENDENCY_UNMET"

    def test_unmet_dependency_includes_details(self, api_client, phase, workplan):
        dep_task = make_task(phase, workplan, "doing")
        task = make_task(phase, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        details = response.data["error"]["details"]
        assert details["dependency_id"] == dep_task.id
        assert details["dependency_status"] == "doing"

    def test_done_dependency_allows_claim(self, api_client, phase, workplan):
        dep_task = make_task(phase, workplan, "done")
        task = make_task(phase, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="task",
            target_id=dep_task.id,
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_nonexistent_target_dependency_skipped(self, api_client, phase, workplan):
        task = make_task(phase, workplan)
        Link.objects.create(
            source_type="task",
            source_id=task.id,
            target_type="external",
            target_id="external-ref-123",
            link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        # External dependency (target task doesn't exist) is skipped
        assert response.status_code == status.HTTP_200_OK

    def test_multiple_deps_all_done_allows_claim(self, api_client, phase, workplan):
        dep1 = make_task(phase, workplan, "done")
        dep2 = make_task(phase, workplan, "done")
        task = make_task(phase, workplan)
        Link.objects.create(
            source_type="task", source_id=task.id, target_type="task",
            target_id=dep1.id, link_type="depends_on",
        )
        Link.objects.create(
            source_type="task", source_id=task.id, target_type="task",
            target_id=dep2.id, link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_one_unmet_dep_among_many_blocks_claim(self, api_client, phase, workplan):
        dep1 = make_task(phase, workplan, "done")
        dep2 = make_task(phase, workplan, "todo")
        task = make_task(phase, workplan)
        Link.objects.create(
            source_type="task", source_id=task.id, target_type="task",
            target_id=dep1.id, link_type="depends_on",
        )
        Link.objects.create(
            source_type="task", source_id=task.id, target_type="task",
            target_id=dep2.id, link_type="depends_on",
        )
        response = api_client.post(
            f"/v1/tasks/{task.id}/claim/", {"agent_id": "agent-1"}, format="json"
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
        user = User.objects.create_user(username='concurrent-test-user')
        token = Token.objects.create(user=user)
        return token.key

    def test_concurrent_claim_one_wins_one_gets_409(self, phase, workplan):
        """Two agents race to claim the same task; exactly one should win."""
        task = make_task(phase, workplan)
        token_key = self._make_token_key()
        results = []

        def do_claim(agent_id):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Token {token_key}')
            resp = client.post(
                f"/v1/tasks/{task.id}/claim/",
                {"agent_id": agent_id},
                format="json",
            )
            results.append(resp.status_code)

        t1 = threading.Thread(target=do_claim, args=("agent-A",))
        t2 = threading.Thread(target=do_claim, args=("agent-B",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert sorted(results) == [200, 409]

    def test_concurrent_claim_task_ends_in_doing(self, phase, workplan):
        """After concurrent claims, task should be in 'doing' state."""
        task = make_task(phase, workplan)
        token_key = self._make_token_key()

        def do_claim(agent_id):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Token {token_key}')
            client.post(
                f"/v1/tasks/{task.id}/claim/",
                {"agent_id": agent_id},
                format="json",
            )

        t1 = threading.Thread(target=do_claim, args=("agent-A",))
        t2 = threading.Thread(target=do_claim, args=("agent-B",))
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
    def test_claimable_returns_todo_tasks(self, api_client, phase, workplan):
        make_task(phase, workplan, "todo", title="Task A")
        make_task(phase, workplan, "todo", title="Task B")
        make_task(phase, workplan, "doing", title="Task C")
        response = api_client.get("/v1/tasks/claimable/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_claimable_excludes_non_todo(self, api_client, phase, workplan):
        make_task(phase, workplan, "draft")
        make_task(phase, workplan, "doing")
        make_task(phase, workplan, "done")
        make_task(phase, workplan, "blocked")
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data) == 0

    def test_claimable_tag_filter_includes_matching(self, api_client, phase, workplan):
        make_task(phase, workplan, requires=["executor"])
        make_task(phase, workplan, requires=[])
        response = api_client.get("/v1/tasks/claimable/?tags=executor")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_claimable_tag_filter_excludes_non_matching(self, api_client, phase, workplan):
        make_task(phase, workplan, requires=["opus"])
        make_task(phase, workplan, requires=["executor"])
        response = api_client.get("/v1/tasks/claimable/?tags=executor")
        assert len(response.data) == 1
        assert response.data[0]["requires"] == ["executor"]

    def test_claimable_no_tags_returns_all_todo(self, api_client, phase, workplan):
        make_task(phase, workplan, requires=["executor"])
        make_task(phase, workplan, requires=[])
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data) == 2

    def test_claimable_excludes_tasks_with_unmet_deps(self, api_client, phase, workplan):
        dep_task = make_task(phase, workplan, "todo", title="Dep")
        task = make_task(phase, workplan, title="Dependent")
        Link.objects.create(
            source_type="task", source_id=task.id, target_type="task",
            target_id=dep_task.id, link_type="depends_on",
        )
        response = api_client.get("/v1/tasks/claimable/")
        ids = [t["id"] for t in response.data]
        assert task.id not in ids

    def test_claimable_includes_tasks_with_met_deps(self, api_client, phase, workplan):
        dep_task = make_task(phase, workplan, "done", title="Dep")
        task = make_task(phase, workplan, title="Dependent")
        Link.objects.create(
            source_type="task", source_id=task.id, target_type="task",
            target_id=dep_task.id, link_type="depends_on",
        )
        response = api_client.get("/v1/tasks/claimable/")
        ids = [t["id"] for t in response.data]
        assert task.id in ids

    def test_claimable_agent_id_excludes_other_assigned(self, api_client, phase, workplan):
        make_task(phase, workplan, assigned_to="agent-other", title="Other's task")
        make_task(phase, workplan, assigned_to=None, title="Unassigned")
        response = api_client.get("/v1/tasks/claimable/?agent_id=agent-1")
        assert len(response.data) == 1
        assert response.data[0]["title"] == "Unassigned"

    def test_claimable_agent_id_includes_own_assigned(self, api_client, phase, workplan):
        make_task(phase, workplan, assigned_to="agent-1", title="My task")
        make_task(phase, workplan, assigned_to=None, title="Unassigned")
        response = api_client.get("/v1/tasks/claimable/?agent_id=agent-1")
        assert len(response.data) == 2

    def test_claimable_no_agent_id_shows_all_todo(self, api_client, phase, workplan):
        make_task(phase, workplan, assigned_to="agent-other")
        make_task(phase, workplan, assigned_to=None)
        response = api_client.get("/v1/tasks/claimable/")
        assert len(response.data) == 2

    def test_claimable_combined_tags_and_deps(self, api_client, phase, workplan):
        dep = make_task(phase, workplan, "done", title="Dep")
        task_with_dep = make_task(phase, workplan, requires=["executor"], title="With dep")
        Link.objects.create(
            source_type="task", source_id=task_with_dep.id, target_type="task",
            target_id=dep.id, link_type="depends_on",
        )
        task_no_dep = make_task(phase, workplan, requires=["executor"], title="No dep")
        response = api_client.get("/v1/tasks/claimable/?tags=executor")
        ids = [t["id"] for t in response.data]
        assert task_with_dep.id in ids
        assert task_no_dep.id in ids
