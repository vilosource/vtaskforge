"""MCP tool: vtf_create_task — create a new task."""
from django.db import transaction

from mcp_server.decorators import handle_errors, require_project_access, serialize_response
from mcp_server.parsers import parse_bool, parse_csv_list, parse_json_or_csv, parse_test_command
from mcp_server.serialization import serialize_task
from mcp_server.server import mcp
from mcp_server.project_context import get_default_project


@mcp.tool()
@handle_errors
@require_project_access("project_id")
@serialize_response
def vtf_create_task(
    title: str,
    project_id: str = "",
    description: str = "",
    labels: str = "",
    spec: str = "",
    agent_model: str = "",
    judge: str = "",
    isolation: str = "",
    milestone_id: str = "",
    workplan_id: str = "",
    acceptance_criteria: str = "",
    requires: str = "",
    depends_on: str = "",
    needs_review_before_start: str = "",
    needs_review_on_completion: str = "",
    test_command: str = "",
) -> dict:
    """Create a new task in draft status.

    Args:
        title: Task title (required)
        project_id: Project ID (uses default if not set)
        description: Task description
        labels: Comma-separated labels
        spec: Task specification text
        agent_model: Model override for executor (e.g. "sonnet", "opus")
        judge: Whether to require judge review ("true"/"false")
        isolation: Execution isolation mode ("worktree", "sequential")
        milestone_id: Milestone to assign to
        workplan_id: Workplan to assign to
        acceptance_criteria: JSON array or comma-separated criteria
        requires: Comma-separated agent tags the claiming executor must
            carry (e.g. "executor,opus"). Stored on Task.requires; the
            claim filter checks that the agent's tags are a superset.
            NOT task dependencies — use `depends_on` for those.
        depends_on: Comma-separated task IDs this task depends on. Each
            target must exist. Creates Link rows with link_type=depends_on;
            the task stays unclaimable until every dependency is `done`.
        needs_review_before_start: Require review before start ("true"/"false")
        needs_review_on_completion: Require review on completion ("true"/"false")
        test_command: Test command as JSON dict or plain string
    """
    from projects.models import Project
    from tasks.models import Task
    from workplans.models import Milestone, Workplan
    from mcp_server.user_context import get_current_user

    if not title:
        return {"error": True, "message": "Cannot create task: 'title' is required."}

    pid = project_id or get_default_project()
    if not pid:
        return {"error": True, "message": "Cannot create task: 'project_id' is required."}

    try:
        project = Project.objects.get(pk=pid)
    except Project.DoesNotExist:
        return {"error": True, "message": f"Project '{pid}' not found."}

    kwargs = {
        "title": title,
        "project": project,
        "description": description,
        "status": "draft",
    }

    # Parse optional fields
    if labels:
        kwargs["labels"] = parse_csv_list(labels)
    if spec:
        kwargs["spec"] = spec
    if agent_model:
        kwargs["agent_model"] = agent_model
    if isolation:
        kwargs["isolation"] = isolation
    if acceptance_criteria:
        kwargs["acceptance_criteria"] = parse_json_or_csv(acceptance_criteria)
    if requires:
        kwargs["requires"] = parse_csv_list(requires)
    if test_command:
        kwargs["test_command"] = parse_test_command(test_command)

    judge_val = parse_bool(judge)
    if judge_val is not None:
        kwargs["judge"] = judge_val

    nrbs = parse_bool(needs_review_before_start)
    if nrbs is not None:
        kwargs["needs_review_before_start"] = nrbs

    nroc = parse_bool(needs_review_on_completion)
    if nroc is not None:
        kwargs["needs_review_on_completion"] = nroc

    if workplan_id:
        try:
            kwargs["workplan"] = Workplan.objects.get(pk=workplan_id)
        except Workplan.DoesNotExist:
            return {"error": True, "message": f"Workplan '{workplan_id}' not found."}

    if milestone_id:
        try:
            kwargs["milestone"] = Milestone.objects.get(pk=milestone_id)
        except Milestone.DoesNotExist:
            return {"error": True, "message": f"Milestone '{milestone_id}' not found."}

    # Set created_by from authenticated user
    user = get_current_user()
    if user:
        kwargs["created_by"] = user

    # Validate depends_on targets exist before creating the task, so we
    # don't leave orphan tasks when a caller typos a dependency ID.
    dep_ids: list[str] = []
    if depends_on:
        dep_ids = parse_csv_list(depends_on)
        existing = set(Task.objects.filter(pk__in=dep_ids).values_list("pk", flat=True))
        missing = [d for d in dep_ids if d not in existing]
        if missing:
            return {
                "error": True,
                "message": f"depends_on target(s) not found: {', '.join(missing)}",
            }

    # Create the task and any dependency Link rows atomically — if link
    # creation fails after the task is persisted, roll the task back too.
    with transaction.atomic():
        task = Task.objects.create(**kwargs)

        if dep_ids:
            from links.models import Link
            link_kwargs = {"created_by": user} if user else {}
            Link.objects.bulk_create([
                Link(
                    source_type="task", source_id=task.id,
                    target_type="task", target_id=dep_id,
                    link_type="depends_on", project=project,
                    **link_kwargs,
                )
                for dep_id in dep_ids
            ])

    return {
        "data": {"task": serialize_task(task)},
        "message": f"Created task '{task.title}' ({task.id}) in project {project.name}.",
        "available_actions": ["vtf_task_detail", "vtf_update_task", "vtf_submit_task"],
    }
