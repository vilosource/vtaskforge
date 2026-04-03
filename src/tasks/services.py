"""
Task service functions — reusable business logic extracted from views.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
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

    # Exclude tasks in non-active milestones
    from django.db.models import Q
    tasks = tasks.filter(
        Q(milestone__isnull=True) | Q(milestone__status="active")
    )

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

        # Status check — todo (new work) and changes_requested (rework) are claimable
        if task.status not in ("todo", "changes_requested"):
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
        perform_transition(task, "doing", trigger_source="claim")
        task.claimed_by = agent_id
        task.claimed_at = timezone.now()
        timeout = task.claim_timeout or timedelta(minutes=DEFAULT_CLAIM_TIMEOUT_MINUTES)
        task.claim_expires_at = timezone.now() + timeout
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

        record_event(task, "claimed", data={"agent_id": agent_id}, trigger_source="claim")

    return task


def get_available_actions(task) -> list:
    """Return the list of valid action names for a task given its current status.

    Derives actions directly from VALID_TRANSITIONS in state_machine.py so that
    the two are always consistent.

    Args:
        task: A Task instance (only task.status is read).

    Returns:
        List of target-status strings that are valid transitions from the
        task's current status.  Empty list for terminal statuses.
    """
    # Defer import to avoid circular dependency (state_machine imports events.services)
    from tasks.state_machine import VALID_TRANSITIONS

    return list(VALID_TRANSITIONS.get(task.status, []))


def get_task_context(task_id: str) -> dict:
    """Return full task context for MCP responses.

    Fetches the task with related data in a small number of queries using
    select_related/prefetch_related, then composes a complete context dict
    suitable for passing to MCP tools.

    Args:
        task_id: PK of the task to fetch.

    Returns:
        Dict containing:
            task        — all task scalar fields
            spec        — raw spec text
            dependencies — result of resolve_dependencies()
            reviews     — list of review dicts
            events      — list of the 20 most recent event dicts
            notes       — list of note dicts
            actions     — list of valid action names (from get_available_actions)

    Raises:
        Task.DoesNotExist: If no task with task_id exists.
    """
    task = (
        Task.objects
        .select_related("project", "workplan", "milestone")
        .prefetch_related("reviews", "events", "notes")
        .get(pk=task_id)
    )

    reviews = [
        {
            "id": r.id,
            "decision": r.decision,
            "reason": r.reason,
            "reviewer_id": r.reviewer_id,
            "reviewer_type": r.reviewer_type,
            "created_at": r.created_at.isoformat(),
        }
        for r in task.reviews.all()
    ]

    # Most-recent 20 events (events are ordered -timestamp by default)
    events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "data": e.data,
            "timestamp": e.timestamp.isoformat(),
            "triggered_by": e.actor.username if e.actor else e.trigger_source,
        }
        for e in task.events.all()[:20]
    ]

    notes = [
        {
            "id": n.id,
            "text": n.text,
            "actor_id": n.actor_id,
            "created_at": n.created_at.isoformat(),
        }
        for n in task.notes.all()
    ]

    return {
        "task": {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "project_id": task.project_id,
            "workplan_id": task.workplan_id,
            "milestone_id": task.milestone_id,
            "acceptance_criteria": task.acceptance_criteria,
            "labels": task.labels,
            "needs_review_before_start": task.needs_review_before_start,
            "needs_review_on_completion": task.needs_review_on_completion,
            "review_return_to": task.review_return_to,
            "requires": task.requires,
            "assigned_to": task.assigned_to,
            "claimed_by": task.claimed_by,
            "claimed_at": task.claimed_at.isoformat() if task.claimed_at else None,
            "claim_expires_at": task.claim_expires_at.isoformat() if task.claim_expires_at else None,
            "created_by": task.created_by,
            "agent_model": task.agent_model,
            "test_command": task.test_command,
            "judge": task.judge,
            "isolation": task.isolation,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        },
        "spec": task.spec,
        "dependencies": resolve_dependencies(task_id),
        "reviews": reviews,
        "events": events,
        "notes": notes,
        "actions": get_available_actions(task),
    }


def get_board_summary(project_id: str = None, workplan_id: str = None) -> dict:
    """Return an aggregated board summary for a project or workplan.

    Uses database-level aggregation to avoid Python-level iteration over large
    querysets.

    Args:
        project_id:  If given, restrict to tasks in this project.
        workplan_id: If given, restrict to tasks in this workplan.
                     Both filters may be applied simultaneously.

    Returns:
        Dict containing:
            counts          — {status: count} for all task statuses
            attention_items — list of task dicts in 'blocked' or 'needs_attention'
            pending_reviews — list of task dicts in 'pending_completion_review'
                              or 'pending_start_review'
            active_agents   — list of {task_id, claimed_by} for tasks in 'doing'
                              with claimed_by set
    """
    qs = Task.objects.all()
    if project_id:
        qs = qs.filter(project_id=project_id)
    if workplan_id:
        qs = qs.filter(workplan_id=workplan_id)

    # Aggregate counts by status in a single query
    counts_qs = qs.values("status").annotate(count=Count("id"))
    counts = {row["status"]: row["count"] for row in counts_qs}

    # Attention items: blocked or needs_attention
    attention_qs = qs.filter(
        Q(status="blocked") | Q(status="needs_attention")
    ).values("id", "title", "status")
    attention_items = list(attention_qs)

    # Pending reviews: waiting for a review decision
    pending_review_qs = qs.filter(
        Q(status="pending_completion_review") | Q(status="pending_start_review")
    ).values("id", "title", "status")
    pending_reviews = list(pending_review_qs)

    # Active agents: tasks in doing status that have a claimed_by value
    active_agents_qs = qs.filter(
        status="doing"
    ).exclude(
        claimed_by__isnull=True
    ).exclude(
        claimed_by=""
    ).values("id", "claimed_by")
    active_agents = list(active_agents_qs)

    return {
        "counts": counts,
        "attention_items": attention_items,
        "pending_reviews": pending_reviews,
        "active_agents": active_agents,
    }
