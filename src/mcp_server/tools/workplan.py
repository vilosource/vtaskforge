"""
MCP tool: vtf_manage_workplan

Unified tool for workplan creation, listing, updates, and status changes.
Wraps the existing WorkplanViewSet REST API as a thin MCP layer.
"""
import json

from django.db.models import Count

from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from mcp_server.utils import _suggest_action
from workplans.models import Workplan

VALID_ACTIONS = ["create", "list", "update", "archive", "complete"]


@mcp.tool()
def vtf_manage_workplan(
    action: str,
    workplan_id: str = "",
    name: str = "",
    description: str = "",
    tags: str = "",
    project_id: str = "",
    status: str = "",
) -> str:
    """Create, list, update, archive, or complete workplans.

    Use this tool to manage the work breakdown structure. Workplans organize
    tasks into milestones within a project. Actions: create, list, update,
    archive, complete.
    """
    if action == "create":
        return _action_create(name, project_id, description, tags)
    elif action == "list":
        return _action_list(project_id, status)
    elif action == "update":
        return _action_update(workplan_id, name, description, tags)
    elif action == "archive":
        return _action_set_status(workplan_id, "archived", "archive")
    elif action == "complete":
        return _action_set_status(workplan_id, "completed", "complete")
    else:
        suggestion = _suggest_action(action, VALID_ACTIONS)
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        message = f"Unknown action '{action}'.{hint} Valid actions: {', '.join(VALID_ACTIONS)}."
        return json.dumps(
            error_response(
                message=message,
                data={"action": action},
                available_actions=["vtf_manage_workplan"],
            )
        )


def _get_workplan(workplan_id: str):
    """Fetch a workplan by ID, returning (workplan, None) or (None, error_json)."""
    try:
        wp = Workplan.objects.get(pk=workplan_id)
        return wp, None
    except Workplan.DoesNotExist:
        err = json.dumps(
            error_response(
                message=f"Workplan {workplan_id} not found.",
                data={"workplan_id": workplan_id},
                available_actions=["vtf_manage_workplan(action=list)"],
            )
        )
        return None, err


def _action_create(name, project_id, description, tags):
    """Create a new workplan in active status."""
    if not name:
        return json.dumps(
            error_response(
                message="Cannot create workplan: 'name' is required.",
                data={},
                available_actions=["vtf_manage_workplan(action=create)"],
            )
        )
    if not project_id:
        return json.dumps(
            error_response(
                message="Cannot create workplan: 'project_id' is required.",
                data={},
                available_actions=["vtf_manage_workplan(action=create)"],
            )
        )

    from projects.models import Project

    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return json.dumps(
            error_response(
                message=(
                    f"Project {project_id} not found. "
                    "Provide a valid project_id when creating a workplan."
                ),
                data={"project_id": project_id},
                available_actions=["vtf_board_overview"],
            )
        )

    kwargs = {
        "name": name,
        "project": project,
        "status": "active",
    }
    if description:
        kwargs["description"] = description
    if tags:
        kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    wp = Workplan.objects.create(**kwargs)

    return json.dumps(
        success_response(
            data={
                "workplan": {
                    "id": wp.id,
                    "name": wp.name,
                    "status": wp.status,
                    "project_id": wp.project_id,
                }
            },
            message=(
                f"Created workplan '{wp.name}' (id={wp.id}) in active status."
            ),
            available_actions=[
                "vtf_manage_workplan(action=list)",
                "vtf_manage_workplan(action=update)",
            ],
        )
    )


def _action_list(project_id, status):
    """List workplans with milestone and task counts."""
    from tasks.models import Task

    qs = Workplan.objects.all()
    if project_id:
        qs = qs.filter(project_id=project_id)
    if status:
        qs = qs.filter(status=status)

    workplans = []
    for wp in qs:
        # Annotate task counts by status
        task_qs = Task.objects.filter(workplan=wp).values("status").annotate(
            count=Count("id")
        )
        task_counts = {row["status"]: row["count"] for row in task_qs}

        workplans.append({
            "id": wp.id,
            "name": wp.name,
            "status": wp.status,
            "project_id": wp.project_id,
            "description": wp.description,
            "tags": wp.tags,
            "milestone_count": wp.milestones.count(),
            "task_counts": task_counts,
        })

    return json.dumps(
        success_response(
            data={"workplans": workplans},
            message=f"Found {len(workplans)} workplan(s).",
            available_actions=[
                "vtf_manage_workplan(action=create)",
                "vtf_manage_workplan(action=update)",
            ],
        )
    )


def _action_update(workplan_id, name, description, tags):
    """Update mutable workplan fields."""
    if not workplan_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot update workplan: 'workplan_id' is required. "
                    "Use vtf_manage_workplan(action=list) to find the workplan."
                ),
                data={},
                available_actions=["vtf_manage_workplan(action=list)"],
            )
        )

    wp, err = _get_workplan(workplan_id)
    if err:
        return err

    update_fields = ["updated_at"]

    if name:
        wp.name = name
        update_fields.append("name")
    if description:
        wp.description = description
        update_fields.append("description")
    if tags:
        wp.tags = [t.strip() for t in tags.split(",") if t.strip()]
        update_fields.append("tags")

    wp.save(update_fields=update_fields)

    return json.dumps(
        success_response(
            data={
                "workplan": {
                    "id": wp.id,
                    "name": wp.name,
                    "status": wp.status,
                }
            },
            message=f"Workplan {wp.id} updated.",
            available_actions=["vtf_manage_workplan(action=list)"],
        )
    )


def _action_set_status(workplan_id, new_status, action_name):
    """Set workplan status (archive or complete)."""
    if not workplan_id:
        return json.dumps(
            error_response(
                message=(
                    f"Cannot {action_name} workplan: 'workplan_id' is required. "
                    "Use vtf_manage_workplan(action=list) to find the workplan."
                ),
                data={},
                available_actions=["vtf_manage_workplan(action=list)"],
            )
        )

    wp, err = _get_workplan(workplan_id)
    if err:
        return err

    previous_status = wp.status
    wp.status = new_status
    wp.save(update_fields=["status", "updated_at"])

    return json.dumps(
        success_response(
            data={
                "workplan": {
                    "id": wp.id,
                    "name": wp.name,
                    "previous_status": previous_status,
                    "status": wp.status,
                }
            },
            message=f"Workplan {wp.id} {action_name}d (was '{previous_status}').",
            available_actions=["vtf_manage_workplan(action=list)"],
        )
    )
