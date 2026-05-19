"""WC-1 — Workgraph Composition contract (vtaskforge, the SoR half).

DAG composition = feature-integration-branch + serialized merge-queue,
made deterministic. vtaskforge owns the *facts and serialization*; the
controller (WC-2) owns the git mechanics.

C1  Milestone-owned integration branch (the fact + activation rule).
C2  Server-derived per-task base_ref (rule lives in the SoR).
C3  'integrating' status + serialized merge point + I4 done-guard.
C4  Workgraph-scope liveness — expire_stale_integrations reaper.

Forks ratified 2026-05-19: F-A server-derived base_ref;
F-B milestone select_for_update + 'integrating' status. OAQ-7 deferred.
See docs/wc1-composition-contract-DESIGN.md.
"""

import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from events.models import TaskEvent
from links.models import Link
from tasks.celery_tasks import expire_stale_integrations
from tasks.exceptions import GuardViolation
from tasks.models import Task
from tasks.services import is_workgraph_task, resolve_base_ref, take_merge_slot
from tasks.state_machine import (
    NON_TERMINAL_STATUSES,
    get_valid_transitions,
    perform_transition,
)
from tests.factories import MilestoneFactory, TaskFactory, WorkplanFactory


# ---------------------------------------------------------------------------
# C1 — Milestone.integration_branch (the fact) + activation rule
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestC1IntegrationBranchFact:
    def test_field_defaults_blank(self):
        m = MilestoneFactory()
        assert m.integration_branch == ""

    def test_activate_single_task_milestone_leaves_blank(self):
        """V16: single-task milestone behaviour byte-identical — no branch."""
        m = MilestoneFactory(status="pending")
        TaskFactory(milestone=m, status="draft")
        from workplans.services import set_integration_branch_on_activate
        set_integration_branch_on_activate(m)
        m.refresh_from_db()
        assert m.integration_branch == ""

    def test_activate_multi_task_milestone_sets_branch(self):
        m = MilestoneFactory(status="pending")
        TaskFactory(milestone=m, status="draft")
        TaskFactory(milestone=m, status="draft")
        from workplans.services import set_integration_branch_on_activate
        set_integration_branch_on_activate(m)
        m.refresh_from_db()
        assert m.integration_branch == f"vafi/wg-{m.id}"

    def test_activate_with_depends_on_edge_sets_branch_even_single(self):
        m = MilestoneFactory(status="pending")
        t1 = TaskFactory(milestone=m, status="draft")
        t2 = TaskFactory(milestone=m, status="draft")
        Link.objects.create(
            source_type="task", source_id=t2.id,
            target_type="task", target_id=t1.id,
            link_type="depends_on",
        )
        from workplans.services import set_integration_branch_on_activate
        set_integration_branch_on_activate(m)
        m.refresh_from_db()
        assert m.integration_branch == f"vafi/wg-{m.id}"

    def test_activate_endpoint_sets_branch(self, api_client):
        m = MilestoneFactory(status="pending")
        TaskFactory(milestone=m, status="draft")
        TaskFactory(milestone=m, status="draft")
        resp = api_client.post(f"/v2/milestones/{m.id}/activate/")
        assert resp.status_code == 200
        m.refresh_from_db()
        assert m.status == "active"
        assert m.integration_branch == f"vafi/wg-{m.id}"


# ---------------------------------------------------------------------------
# C2 — server-derived base_ref (the rule lives in the SoR)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestC2BaseRefResolver:
    def test_milestone_with_integration_branch(self):
        m = MilestoneFactory(integration_branch="vafi/wg-abc")
        t = TaskFactory(milestone=m)
        assert resolve_base_ref(t) == "vafi/wg-abc"

    def test_milestone_without_branch_falls_back_to_project_default(self):
        wp = WorkplanFactory()
        wp.project.default_branch = "develop"
        wp.project.save()
        m = MilestoneFactory(workplan=wp, integration_branch="")
        t = TaskFactory(milestone=m)
        assert resolve_base_ref(t) == "develop"

    def test_no_milestone_falls_back_to_project_default(self):
        from tests.factories import BacklogTaskFactory
        t = BacklogTaskFactory()
        t.project.default_branch = "main"
        t.project.save()
        assert resolve_base_ref(t) == "main"

    def test_v2_serializer_exposes_base_ref(self, api_client):
        m = MilestoneFactory(integration_branch="vafi/wg-xyz")
        t = TaskFactory(milestone=m)
        resp = api_client.get(f"/v2/tasks/{t.id}/")
        assert resp.status_code == 200
        assert resp.data["base_ref"] == "vafi/wg-xyz"


# ---------------------------------------------------------------------------
# C3 — 'integrating' status, edges, I4 done-guard, serialized merge slot
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestC3StateMachine:
    def test_integrating_is_non_terminal(self):
        assert "integrating" in NON_TERMINAL_STATUSES

    def test_pcr_can_go_to_integrating(self):
        assert "integrating" in get_valid_transitions("pending_completion_review")

    def test_pcr_existing_transitions_unchanged(self):
        v = set(get_valid_transitions("pending_completion_review"))
        assert {"done", "changes_requested", "cancelled", "needs_attention"}.issubset(v)

    def test_integrating_edges(self):
        v = set(get_valid_transitions("integrating"))
        assert {"done", "needs_attention"}.issubset(v)

    def test_workgraph_task_cannot_reach_done_without_integrating(self):
        m = MilestoneFactory(integration_branch="vafi/wg-1")
        t = TaskFactory(milestone=m, status="pending_completion_review")
        with pytest.raises(GuardViolation):
            perform_transition(t, "done")

    def test_workgraph_task_reaches_done_via_integrating(self):
        m = MilestoneFactory(integration_branch="vafi/wg-1")
        t = TaskFactory(milestone=m, status="integrating")
        perform_transition(t, "done")
        t.refresh_from_db()
        assert t.status == "done"

    def test_non_workgraph_task_done_path_unchanged(self):
        """V16 — single-task / no integration branch goes straight to done."""
        m = MilestoneFactory(integration_branch="")
        t = TaskFactory(milestone=m, status="pending_completion_review")
        perform_transition(t, "done")
        t.refresh_from_db()
        assert t.status == "done"


@pytest.mark.django_db
class TestC3MergeSlotSerialization:
    def test_take_merge_slot_moves_pcr_to_integrating(self):
        m = MilestoneFactory(integration_branch="vafi/wg-1")
        t = TaskFactory(milestone=m, status="pending_completion_review")
        take_merge_slot(t)
        t.refresh_from_db()
        assert t.status == "integrating"

    def test_only_one_in_flight_integration_per_milestone(self):
        m = MilestoneFactory(integration_branch="vafi/wg-1")
        t1 = TaskFactory(milestone=m, status="integrating")
        t2 = TaskFactory(milestone=m, status="pending_completion_review")
        with pytest.raises(Exception):
            take_merge_slot(t2)
        t2.refresh_from_db()
        assert t2.status == "pending_completion_review"

    def test_is_workgraph_task(self):
        m1 = MilestoneFactory(integration_branch="vafi/wg-1")
        m2 = MilestoneFactory(integration_branch="")
        assert is_workgraph_task(TaskFactory(milestone=m1)) is True
        assert is_workgraph_task(TaskFactory(milestone=m2)) is False


# ---------------------------------------------------------------------------
# C4 — expire_stale_integrations (I2 at DAG granularity)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestC4IntegrationReaper:
    def _integrating(self, expires_delta):
        m = MilestoneFactory(integration_branch="vafi/wg-1")
        t = TaskFactory(milestone=m, status="integrating")
        t.integration_expires_at = timezone.now() + expires_delta
        t.save(update_fields=["integration_expires_at"])
        return t

    def test_stale_integration_escalates_to_needs_attention(self):
        t = self._integrating(timedelta(minutes=-1))
        n = expire_stale_integrations()
        t.refresh_from_db()
        assert n >= 1
        assert t.status == "needs_attention"
        assert TaskEvent.objects.filter(
            task=t, event_type="integration_expired"
        ).exists()

    def test_fresh_integration_untouched(self):
        t = self._integrating(timedelta(minutes=30))
        expire_stale_integrations()
        t.refresh_from_db()
        assert t.status == "integrating"

    def test_no_cross_talk_with_claim_and_review_reapers(self):
        """The integration reaper must not touch doing / pcr tasks."""
        doing = TaskFactory(status="doing")
        pcr = TaskFactory(status="pending_completion_review")
        self._integrating(timedelta(minutes=-1))
        expire_stale_integrations()
        doing.refresh_from_db()
        pcr.refresh_from_db()
        assert doing.status == "doing"
        assert pcr.status == "pending_completion_review"

    def test_entering_integrating_sets_lease(self):
        m = MilestoneFactory(integration_branch="vafi/wg-1")
        t = TaskFactory(milestone=m, status="pending_completion_review")
        assert t.integration_expires_at is None
        perform_transition(t, "integrating")
        t.refresh_from_db()
        assert t.integration_expires_at is not None
        assert t.integration_expires_at > timezone.now()
