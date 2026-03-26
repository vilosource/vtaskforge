"""
MCP tool: vtf_manage_milestone

Unified tool for milestone creation, listing, updates, and state transitions.
Wraps the existing MilestoneViewSet REST API as a thin MCP layer.
"""
import json

from django.db.models import Count

from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from mcp_server.utils import _suggest_action
from workplans.models import Milestone, Workplan

VALID_ACTIONS = ["create", "list", "update", "activate", "complete", "delete"]


@mcp.tool()
def vtf_manage_milestone(
    action: str,
    milestone_id: str = "",
    workplan_id: str = "",
    name: str = "",
    description: str = "",
    order: str = "",
) -> str:
    """Create, list, update, or manage milestones within a workplan.

    Use this to organize tasks into milestones. Actions: create, list, update,
    activate, complete, delete.
    """
    if action == "create":
        return _action_create(workplan_id, name, description, order)
    elif action == "list":
        return _action_list(workplan_id)
    elif action == "update":
        return _action_update(milestone_id, name, description, order)
    elif action == "activate":
        return _action_transition(milestone_id, "activate", "pending", "active")
    elif action == "complete":
        return _action_transition(milestone_id, "complete", "active", "completed")
    elif action == "delete":
        return _action_delete(milestone_id)
    else:
        suggestion = _suggest_action(action, VALID_ACTIONS)
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        message = f"Unknown action '{action}'.{hint} Valid actions: {', '.join(VALID_ACTIONS)}."
        return json.dumps(
            error_response(
                message=message,
                data={"action": action},
                available_actions=["vtf_manage_milestone"],
            )
        )


def _get_milestone(milestone_id: str):
    """Fetch a milestone by ID, returning (milestone, None) or (None, error_json)."""
    try:
        m = Milestone.objects.get(pk=milestone_id)
        return m, None
    except Milestone.DoesNotExist:
        err = json.dumps(
            error_response(
                message=f"Milestone {milestone_id} not found.",
                data={"milestone_id": milestone_id},
                available_actions=["vtf_manage_milestone(action=list)"],
            )
        )
        return None, err


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


def _action_create(workplan_id, name, description, order):
    """Create a new milestone in pending status."""
    if not name:
        return json.dumps(
            error_response(
                message="Cannot create milestone: 'name' is required.",
                data={},
                available_actions=["vtf_manage_milestone(action=create)"],
            )
        )
    if not workplan_id:
        return json.dumps(
            error_response(
                message="Cannot create milestone: 'workplan_id' is required.",
                data={},
                available_actions=["vtf_manage_milestone(action=create)"],
            )
        )

    wp, err = _get_workplan(workplan_id)
    if err:
        return err

    order_int = int(order) if order else 0

    kwargs = {
        "name": name,
        "workplan": wp,
        "order": order_int,
    }
    if description:
        kwargs["description"] = description

    m = Milestone.objects.create(**kwargs)

    return json.dumps(
        success_response(
            data={
                "milestone": {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "order": m.order,
                    "workplan_id": m.workplan_id,
                    "description": m.description,
                }
            },
            message=f"Created milestone '{m.name}' (id={m.id}) in pending status.",
            available_actions=[
                "vtf_manage_milestone(action=list)",
                "vtf_manage_milestone(action=activate)",
            ],
        )
    )


def _action_list(workplan_id):
    """List milestones for a workplan ordered by order field with task counts."""
    if not workplan_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot list milestones: 'workplan_id' is required. "
                    "Use vtf_manage_workplan(action=list) to find a workplan."
                ),
                data={},
                available_actions=["vtf_manage_workplan(action=list)"],
            )
        )

    wp, err = _get_workplan(workplan_id)
    if err:
        return err

    from tasks.models import Task

    milestones = []
    for m in Milestone.objects.filter(workplan=wp).order_by("order", "created_at"):
        task_qs = Task.objects.filter(milestone=m).values("status").annotate(
            count=Count("id")
        )
        task_counts = {row["status"]: row["count"] for row in task_qs}

        milestones.append({
            "id": m.id,
            "name": m.name,
            "status": m.status,
            "order": m.order,
            "description": m.description,
            "task_counts": task_counts,
        })

    return json.dumps(
        success_response(
            data={"milestones": milestones},
            message=f"Found {len(milestones)} milestone(s) for workplan {workplan_id}.",
            available_actions=[
                "vtf_manage_milestone(action=create)",
                "vtf_manage_milestone(action=activate)",
            ],
        )
    )


def _action_update(milestone_id, name, description, order):
    """Update mutable milestone fields."""
    if not milestone_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot update milestone: 'milestone_id' is required. "
                    "Use vtf_manage_milestone(action=list) to find the milestone."
                ),
                data={},
                available_actions=["vtf_manage_milestone(action=list)"],
            )
        )

    m, err = _get_milestone(milestone_id)
    if err:
        return err

    update_fields = ["updated_at"]

    if name:
        m.name = name
        update_fields.append("name")
    if description:
        m.description = description
        update_fields.append("description")
    if order:
        m.order = int(order)
        update_fields.append("order")

    m.save(update_fields=update_fields)

    return json.dumps(
        success_response(
            data={
                "milestone": {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "order": m.order,
                }
            },
            message=f"Milestone {m.id} updated.",
            available_actions=["vtf_manage_milestone(action=list)"],
        )
    )


def _action_transition(milestone_id, action_name, required_status, new_status):
    """Transition milestone status with validation."""
    if not milestone_id:
        return json.dumps(
            error_response(
                message=(
                    f"Cannot {action_name} milestone: 'milestone_id' is required. "
                    "Use vtf_manage_milestone(action=list) to find the milestone."
                ),
                data={},
                available_actions=["vtf_manage_milestone(action=list)"],
            )
        )

    m, err = _get_milestone(milestone_id)
    if err:
        return err

    if m.status != required_status:
        return json.dumps(
            error_response(
                message=(
                    f"Cannot {action_name} milestone '{m.id}': "
                    f"expected status '{required_status}' but current status is '{m.status}'. "
                    f"Only milestones in '{required_status}' status can be {action_name}d."
                ),
                data={"milestone_id": m.id, "current_status": m.status, "required_status": required_status},
                available_actions=["vtf_manage_milestone(action=list)"],
            )
        )

    previous_status = m.status
    m.status = new_status
    m.save(update_fields=["status", "updated_at"])

    return json.dumps(
        success_response(
            data={
                "milestone": {
                    "id": m.id,
                    "name": m.name,
                    "previous_status": previous_status,
                    "status": m.status,
                }
            },
            message=f"Milestone {m.id} {action_name}d (was '{previous_status}').",
            available_actions=["vtf_manage_milestone(action=list)"],
        )
    )


def _action_delete(milestone_id):
    """Delete a milestone (tasks become orphans in the workplan)."""
    if not milestone_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot delete milestone: 'milestone_id' is required. "
                    "Use vtf_manage_milestone(action=list) to find the milestone."
                ),
                data={},
                available_actions=["vtf_manage_milestone(action=list)"],
            )
        )

    m, err = _get_milestone(milestone_id)
    if err:
        return err

    m_id = m.id
    m_name = m.name
    m.delete()

    return json.dumps(
        success_response(
            data={"deleted_milestone_id": m_id},
            message=f"Milestone '{m_name}' (id={m_id}) deleted.",
            available_actions=["vtf_manage_milestone(action=list)"],
        )
    )
