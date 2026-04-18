"""MCP tool: vtf_update_task — update task fields."""
from django.db import transaction

from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.parsers import parse_bool, parse_csv_list, parse_json_or_csv, parse_test_command
from mcp_server.serialization import serialize_task
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_update_task(
    task_id: str,
    title: str = "",
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
    """Update fields on an existing task.

    Only provided (non-empty) fields are updated. The task must exist.

    `depends_on` uses REPLACE semantics: the comma-separated list of task
    IDs becomes the task's full set of depends_on Links — existing
    depends_on links are deleted, then new Link rows are created for each
    target (targets must exist). Pass an empty string to leave deps
    untouched. To explicitly clear all deps, see vtf_delete_link.
    """
    from tasks.models import Task
    from workplans.models import Milestone, Workplan

    if not task_id:
        return {"error": True, "message": "task_id is required."}

    try:
        task = Task.objects.select_related(
            "project", "workplan", "milestone", "assigned_to", "claimed_by", "created_by",
        ).get(pk=task_id)
    except Task.DoesNotExist:
        return {"error": True, "message": f"Task '{task_id}' not found."}

    updates = {}
    if title:
        updates["title"] = title
    if description:
        updates["description"] = description
    if labels:
        updates["labels"] = parse_csv_list(labels)
    if spec:
        updates["spec"] = spec
    if agent_model:
        updates["agent_model"] = agent_model
    if isolation:
        updates["isolation"] = isolation
    if acceptance_criteria:
        updates["acceptance_criteria"] = parse_json_or_csv(acceptance_criteria)
    if requires:
        updates["requires"] = parse_csv_list(requires)
    if test_command:
        updates["test_command"] = parse_test_command(test_command)

    judge_val = parse_bool(judge)
    if judge_val is not None:
        updates["judge"] = judge_val

    nrbs = parse_bool(needs_review_before_start)
    if nrbs is not None:
        updates["needs_review_before_start"] = nrbs

    nroc = parse_bool(needs_review_on_completion)
    if nroc is not None:
        updates["needs_review_on_completion"] = nroc

    if workplan_id:
        try:
            updates["workplan"] = Workplan.objects.get(pk=workplan_id)
        except Workplan.DoesNotExist:
            return {"error": True, "message": f"Workplan '{workplan_id}' not found."}

    if milestone_id:
        try:
            updates["milestone"] = Milestone.objects.get(pk=milestone_id)
        except Milestone.DoesNotExist:
            return {"error": True, "message": f"Milestone '{milestone_id}' not found."}

    # Validate depends_on targets exist before touching anything.
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

    if not updates and not depends_on:
        return {"error": True, "message": "No fields to update. Provide at least one field."}

    with transaction.atomic():
        if updates:
            for field, value in updates.items():
                setattr(task, field, value)
            task.save(update_fields=list(updates.keys()) + ["updated_at"])

        if depends_on:
            from links.models import Link
            # Replace semantics: drop existing depends_on, recreate from list
            Link.objects.filter(
                source_type="task", source_id=task.id, link_type="depends_on",
            ).delete()
            if dep_ids:
                from mcp_server.user_context import get_current_user
                user = get_current_user()
                link_kwargs = {"created_by": user} if user else {}
                Link.objects.bulk_create([
                    Link(
                        source_type="task", source_id=task.id,
                        target_type="task", target_id=dep_id,
                        link_type="depends_on", project=task.project,
                        **link_kwargs,
                    )
                    for dep_id in dep_ids
                ])

    task.refresh_from_db()
    changed = list(updates.keys())
    if depends_on:
        changed.append("depends_on")
    return {
        "data": {"task": serialize_task(task)},
        "message": f"Updated task '{task.title}' ({task.id}). Changed: {', '.join(changed)}.",
        "available_actions": ["vtf_task_detail", "vtf_submit_task"],
    }
