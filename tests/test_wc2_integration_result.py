"""WC-2 reporting seam — the controller-facing integration-result API.

Completes WC-1/C3's "controller reports the outcome" half (no consumer
existed at WC-1 time; WC-2's vafi controller is now it). Symmetric
counterpart to take_merge_slot. State-machine-bounded, idempotent,
re-entrant with the WC-1/C4 reaper. See
vafi/docs/wc2-controller-integration-DESIGN.md (SEAM).
"""

import pytest

from events.models import TaskEvent
from tasks.models import Note
from tests.factories import MilestoneFactory, TaskFactory


@pytest.mark.django_db
class TestIntegrationResultEndpoint:
    def _wg_task(self, status):
        m = MilestoneFactory(integration_branch="vafi/wg-1")
        return TaskFactory(milestone=m, status=status)

    def test_success_integrating_to_done(self, api_client):
        t = self._wg_task("integrating")
        resp = api_client.post(
            f"/v2/tasks/{t.id}/integration-result/",
            {"success": True, "detail": "merged abc123"}, format="json",
        )
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.status == "done"
        assert TaskEvent.objects.filter(
            task=t, event_type="integration_succeeded"
        ).exists()

    def test_conflict_integrating_to_needs_attention_with_note(self, api_client):
        t = self._wg_task("integrating")
        resp = api_client.post(
            f"/v2/tasks/{t.id}/integration-result/",
            {"success": False, "detail": "CONFLICT (content): src/a.py"},
            format="json",
        )
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.status == "needs_attention"
        assert Note.objects.filter(
            task=t, text__contains="CONFLICT (content): src/a.py"
        ).exists()
        assert TaskEvent.objects.filter(
            task=t, event_type="integration_failed"
        ).exists()

    def test_idempotent_already_done(self, api_client):
        """A second success report (or a report after the C4 reaper /
        a prior call) is a no-op, not an error."""
        t = self._wg_task("done")
        resp = api_client.post(
            f"/v2/tasks/{t.id}/integration-result/",
            {"success": True, "detail": ""}, format="json",
        )
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.status == "done"

    def test_idempotent_already_needs_attention(self, api_client):
        """Reaper (WC-1/C4) raced the controller report → no-op."""
        t = self._wg_task("needs_attention")
        resp = api_client.post(
            f"/v2/tasks/{t.id}/integration-result/",
            {"success": False, "detail": "late conflict"}, format="json",
        )
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.status == "needs_attention"

    def test_misuse_non_integration_state_rejected(self, api_client):
        t = self._wg_task("doing")
        resp = api_client.post(
            f"/v2/tasks/{t.id}/integration-result/",
            {"success": True, "detail": ""}, format="json",
        )
        assert resp.status_code == 409
        t.refresh_from_db()
        assert t.status == "doing"

    def test_missing_success_field_is_422(self, api_client):
        t = self._wg_task("integrating")
        resp = api_client.post(
            f"/v2/tasks/{t.id}/integration-result/",
            {"detail": "no success key"}, format="json",
        )
        assert resp.status_code == 422
        t.refresh_from_db()
        assert t.status == "integrating"
