"""Workplan / milestone domain services.

WC-1/C1: the milestone-activation rule that assigns the integration
branch *name*. A milestone composes a DAG (and therefore needs a shared
integration branch) when it has ≥2 tasks OR any task carries a
depends_on edge. Single, independent tasks leave the branch blank so
base_ref falls back to project.default_branch (V16 — unchanged).
"""

from links.models import Link


def milestone_needs_integration_branch(milestone) -> bool:
    """True iff this milestone composes a DAG: ≥2 tasks, or any task in
    the milestone has a depends_on edge."""
    task_ids = list(
        milestone.tasks.values_list("id", flat=True)  # type: ignore[attr-defined]
    )
    if len(task_ids) >= 2:
        return True
    if not task_ids:
        return False
    return Link.objects.filter(
        source_type="task",
        source_id__in=task_ids,
        link_type="depends_on",
    ).exists()


def set_integration_branch_on_activate(milestone) -> None:
    """Idempotently assign the integration-branch *name* when a
    qualifying milestone is activated. vtaskforge records the name only;
    the controller (WC-2) creates the git ref. No-op if already set or
    if the milestone is a single independent task."""
    if milestone.integration_branch:
        return
    if milestone_needs_integration_branch(milestone):
        milestone.integration_branch = f"vafi/wg-{milestone.id}"
        milestone.save(update_fields=["integration_branch", "updated_at"])
