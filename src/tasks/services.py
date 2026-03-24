"""
Task service functions — reusable business logic extracted from views.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from events.services import record_event
from links.models import Link
from tasks.models import Task

DEFAULT_CLAIM_TIMEOUT_MINUTES = 30


class ClaimError(Exception):
    """Raised by claim_task() when a claim attempt fails validation.

    Attributes:
        message:     Human-readable description of the failure.
        code:        Machine-readable error type (e.g. "tag_mismatch").
        status_code: Suggested HTTP status code the view should return.
        details:     Optional dict of extra context for the error response.
    """

    def __init__(self, message: str, code: str, status_code: int = 422, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


def resolve_dependencies(task_id: str) -> dict:
    """Check if all depends_on links for a task point to done tasks.

    Returns a dict with:
        resolved (bool): True if all dependencies are satisfied.
        dependencies (list): All dependency info dicts with id, title, status.
        unresolved (list): Subset of dependencies that are not done.

    External dependencies (target task not found in DB) are skipped — they do
    not block resolution, consistent with the inline claim() behaviour.
    """
    depends_on_links = Link.objects.filter(
        source_type="task", source_id=task_id, link_type="depends_on"
    )

    dependencies = []
    unresolved = []

    for link in depends_on_links:
        try:
            dep_task = Task.objects.get(pk=link.target_id)
        except Task.DoesNotExist:
            # External / dangling reference — skip (not treated as blocking)
            continue

        dep_info = {
            "id": dep_task.id,
            "title": dep_task.title,
            "status": dep_task.status,
        }
        dependencies.append(dep_info)
        if dep_task.status != "done":
            unresolved.append(dep_info)

    return {
        "resolved": len(unresolved) == 0,
        "dependencies": dependencies,
        "unresolved": unresolved,
    }


def get_tasks_with_unresolved_deps(task_ids: list) -> set:
    """Given a list of task IDs, return the subset that have unresolved dependencies.

    A task has unresolved deps when at least one of its depends_on link targets
    exists in the DB and is not in 'done' status. Tasks whose dependency links
    all point to external/nonexistent targets are considered resolved.

    Used by claimable() to efficiently filter out tasks that cannot yet be claimed.
    """
    if not task_ids:
        return set()

    # Only look at task IDs that actually have depends_on links
    task_ids_with_deps = set(
        Link.objects.filter(
            source_type="task",
            source_id__in=task_ids,
            link_type="depends_on",
        ).values_list("source_id", flat=True)
    )

    unresolved_ids = set()
    for tid in task_ids_with_deps:
        result = resolve_dependencies(tid)
        if not result["resolved"]:
            unresolved_ids.add(tid)

    return unresolved_ids


def find_claimable_tasks(
    project_id: str = None,
    tags: list = None,
    agent_id: str = None,
) -> list:
    """Return tasks that are claimable, optionally filtered by project, tags, and agent.

    Finds tasks in 'todo' status, excludes tasks with unresolved dependencies,
    filters by tag matching (task.requires must be a subset of given tags),
    and filters by assignment (unassigned or assigned to agent_id).

    Args:
        project_id: If given, only return tasks belonging to this project.
        tags:       Agent's capability tags. If provided, task.requires must be
                    a subset of these tags. If None or empty, tag filtering is skipped.
        agent_id:   If given, exclude tasks assigned to other agents.

    Returns:
        QuerySet of Task objects matching all filters.
    """
    tasks = Task.objects.filter(status="todo")

    if project_id:
        tasks = tasks.filter(project_id=project_id)

    # Exclude tasks with unmet dependencies
    all_task_ids = list(tasks.values_list("id", flat=True))
    unmet_task_ids = get_tasks_with_unresolved_deps(all_task_ids)
    tasks = tasks.exclude(id__in=unmet_task_ids)

    # Filter by tags if provided — task.requires must be subset of provided tags
    if tags:
        filtered_ids = [t.id for t in tasks if not t.requires or set(t.requires).issubset(set(tags))]
        tasks = tasks.filter(id__in=filtered_ids)

    # Filter by assignment — exclude tasks assigned to other agents
    if agent_id:
        unassigned = tasks.filter(assigned_to__isnull=True) | tasks.filter(assigned_to="")
        assigned_to_me = tasks.filter(assigned_to=agent_id)
        tasks = Task.objects.filter(
            id__in=list(unassigned.values_list("id", flat=True))
            + list(assigned_to_me.values_list("id", flat=True))
        )

    return tasks


def claim_task(task_id: str, agent_id: str, agent_tags: list = None) -> Task:
    """Atomically claim a task for an agent.

    Validates status, assignment, tag requirements, and dependency resolution,
    then transitions the task to 'doing' and sets claim fields.

    Args:
        task_id:    PK of the task to claim.
        agent_id:   ID of the agent claiming the task.
        agent_tags: Tags the agent presents for matching against task.requires.
                    Pass None to indicate no tag constraint (empty list is also
                    accepted and treated as an empty tag set).

    Returns:
        The claimed Task instance (refreshed after save).

    Raises:
        ClaimError: On any validation failure. The .status_code attribute
                    carries the appropriate HTTP status for the view to return.
        Task.DoesNotExist: If the task_id is not found (callers may catch this
                    separately to return a 404 before entering the atomic block).
    """
    # Defer import to avoid circular dependency (state_machine imports events.services)
    from tasks.state_machine import perform_transition

    if agent_tags is None:
        agent_tags = []

    with transaction.atomic():
        try:
            task = Task.objects.select_for_update().get(pk=task_id)
        except Task.DoesNotExist:
            raise

        # Status check
        if task.status != "todo":
            raise ClaimError(
                message="Task is not claimable",
                code="ALREADY_CLAIMED",
                status_code=409,
                details={"current_status": task.status},
            )

        # Assignment check
        if task.assigned_to and task.assigned_to != agent_id:
            raise ClaimError(
                message="Task assigned to another agent",
                code="FORBIDDEN",
                status_code=403,
            )

        # Tag matching — task.requires must be subset of agent_tags
        if task.requires:
            if not set(task.requires).issubset(set(agent_tags)):
                raise ClaimError(
                    message="Agent tags do not match task requirements",
                    code="tag_mismatch",
                    status_code=422,
                    details={
                        "requires": task.requires,
                        "agent_tags": agent_tags,
                    },
                )

        # Dependency check
        dep_result = resolve_dependencies(task.id)
        if not dep_result["resolved"]:
            first_unresolved = dep_result["unresolved"][0]
            raise ClaimError(
                message=f"Dependency {first_unresolved['id']} not done",
                code="deps_unmet",
                status_code=422,
                details={
                    "dependency_id": first_unresolved["id"],
                    "dependency_status": first_unresolved["status"],
                },
            )

        # All checks passed — perform claim
        perform_transition(task, "doing", triggered_by=agent_id)
        task.claimed_by = agent_id
        task.claimed_at = timezone.now()
        timeout = task.claim_timeout or timedelta(minutes=DEFAULT_CLAIM_TIMEOUT_MINUTES)
        task.claim_expires_at = timezone.now() + timeout
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

        record_event(task, "claimed", data={"agent_id": agent_id}, triggered_by=agent_id)

    return task
