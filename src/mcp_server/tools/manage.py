"""
MCP tool: vtf_manage_task (P3.3)

Unified tool for task creation, updates, and lifecycle transitions.
Combines CRUD and state management into a single tool with an 'action' parameter.
"""
import json

from events.services import record_event
from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from mcp_server.utils import _suggest_action
from tasks.exceptions import InvalidTransition
from tasks.models import Task
from tasks.state_machine import get_valid_transitions, perform_transition

VALID_ACTIONS = [
    "create", "update", "submit", "block", "unblock",
    "defer", "cancel", "delete", "assign", "unassign",
]


@mcp.tool()
def vtf_manage_task(
    action: str,
    task_id: str = "",
    title: str = "",
    project_id: str = "",
    description: str = "",
    labels: str = "",
    spec: str = "",
    agent_model: str = "",
    judge: str = "",
    isolation: str = "",
    milestone_id: str = "",
    workplan_id: str = "",
    assigned_to: str = "",
    reason: str = "",
    acceptance_criteria: str = "",
    requires: str = "",
    needs_review_before_start: str = "",
    needs_review_on_completion: str = "",
    test_command: str = "",
) -> str:
    """Create, update, or change the status of a task.

    Use the 'action' parameter to specify the operation. For status changes,
    only valid transitions are allowed — the error message will tell you what
    transitions are available from the current status.
    """
    # Route by action
    if action == "create":
        return _action_create(title, project_id, description, labels, spec,
                               agent_model, judge, isolation, milestone_id, workplan_id,
                               acceptance_criteria, requires, needs_review_before_start,
                               needs_review_on_completion, test_command)
    elif action == "update":
        return _action_update(task_id, title, description, labels, spec,
                               agent_model, judge, isolation, milestone_id, workplan_id,
                               acceptance_criteria, requires, needs_review_before_start,
                               needs_review_on_completion, test_command)
    elif action == "submit":
        return _action_transition(task_id, "todo", "submitted")
    elif action == "block":
        return _action_block(task_id, reason)
    elif action == "unblock":
        return _action_transition(task_id, "todo", "unblocked")
    elif action == "defer":
        return _action_transition(task_id, "deferred", "deferred")
    elif action == "cancel":
        return _action_transition(task_id, "cancelled", "cancelled")
    elif action == "delete":
        return _action_delete(task_id)
    elif action == "assign":
        return _action_assign(task_id, assigned_to)
    elif action == "unassign":
        return _action_unassign(task_id)
    else:
        suggestion = _suggest_action(action, VALID_ACTIONS)
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        message = f"Unknown action '{action}'.{hint} Valid actions: {', '.join(VALID_ACTIONS)}."
        return json.dumps(
            error_response(
                message=message,
                data={"action": action},
                available_actions=["vtf_manage_task"],
            )
        )


def _get_task(task_id: str):
    """Fetch a task by ID, returning (task, None) or (None, error_json)."""
    try:
        task = Task.objects.get(pk=task_id)
        return task, None
    except Task.DoesNotExist:
        err = json.dumps(
            error_response(
                message=f"Task {task_id} not found.",
                data={"task_id": task_id},
                available_actions=["vtf_next_work"],
            )
        )
        return None, err


def _action_create(title, project_id, description, labels, spec,
                   agent_model, judge, isolation, milestone_id, workplan_id="",
                   acceptance_criteria="", requires="", needs_review_before_start="",
                   needs_review_on_completion="", test_command=""):
    """Create a new task in draft status."""
    if not title:
        return json.dumps(
            error_response(
                message="Cannot create task: 'title' is required.",
                data={},
                available_actions=["vtf_manage_task(action=create)"],
            )
        )
    if not project_id:
        return json.dumps(
            error_response(
                message="Cannot create task: 'project_id' is required.",
                data={},
                available_actions=["vtf_manage_task(action=create)"],
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
                    "Provide a valid project_id when creating a task."
                ),
                data={"project_id": project_id},
                available_actions=["vtf_board_overview"],
            )
        )

    # Parse labels from comma-separated string
    labels_list = []
    if labels:
        labels_list = [lbl.strip() for lbl in labels.split(",") if lbl.strip()]

    # Parse judge boolean from string
    judge_bool = False
    if judge and judge.lower() in ("true", "1", "yes"):
        judge_bool = True

    # Build kwargs — only set non-empty optional fields
    kwargs = {
        "title": title,
        "project": project,
        "status": "draft",
    }
    if description:
        kwargs["description"] = description
    if labels_list:
        kwargs["labels"] = labels_list
    if spec:
        kwargs["spec"] = spec
    if agent_model:
        kwargs["agent_model"] = agent_model
    if judge:
        kwargs["judge"] = judge_bool
    if isolation:
        kwargs["isolation"] = isolation

    # Resolve optional workplan (milestone_id takes precedence if both provided)
    if workplan_id:
        from workplans.models import Workplan
        try:
            workplan = Workplan.objects.get(pk=workplan_id)
            kwargs["workplan"] = workplan
        except Workplan.DoesNotExist:
            return json.dumps(error_response(
                message=f"Workplan {workplan_id} not found.",
                data={"workplan_id": workplan_id},
                available_actions=["vtf_board_overview"],
            ))

    # Resolve optional milestone (overwrites workplan from above if set)
    if milestone_id:
        from workplans.models import Milestone

        try:
            milestone = Milestone.objects.get(pk=milestone_id)
            kwargs["milestone"] = milestone
            kwargs["workplan"] = milestone.workplan
        except Milestone.DoesNotExist:
            pass

    # acceptance_criteria — JSON array or comma-separated string
    if acceptance_criteria:
        try:
            kwargs["acceptance_criteria"] = json.loads(acceptance_criteria)
        except json.JSONDecodeError:
            kwargs["acceptance_criteria"] = [c.strip() for c in acceptance_criteria.split(",") if c.strip()]

    # requires — comma-separated task IDs, validate they exist
    if requires:
        req_ids = [r.strip() for r in requires.split(",") if r.strip()]
        existing = set(Task.objects.filter(pk__in=req_ids).values_list("pk", flat=True))
        missing = set(req_ids) - existing
        if missing:
            return json.dumps(error_response(
                message=f"Required task(s) not found: {', '.join(missing)}",
                data={"missing_ids": list(missing)},
                available_actions=["vtf_search_tasks"],
            ))
        kwargs["requires"] = req_ids

    # needs_review_before_start
    if needs_review_before_start:
        kwargs["needs_review_before_start"] = needs_review_before_start.lower() in ("true", "1", "yes")

    # needs_review_on_completion
    if needs_review_on_completion:
        kwargs["needs_review_on_completion"] = needs_review_on_completion.lower() in ("true", "1", "yes")

    # test_command — JSON dict
    if test_command:
        try:
            kwargs["test_command"] = json.loads(test_command)
        except json.JSONDecodeError:
            return json.dumps(error_response(
                message="test_command must be valid JSON (e.g. '{\"unit\": \"pytest tests/...\"}').",
                data={},
                available_actions=["vtf_manage_task"],
            ))

    task = Task.objects.create(**kwargs)

    return json.dumps(
        success_response(
            data={
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                }
            },
            message=(
                f"Created task {task.id} in draft status. "
                "Submit it when ready for execution."
            ),
            available_actions=[
                "vtf_manage_task(action=submit)",
                "vtf_manage_task(action=update)",
                "vtf_task_detail",
            ],
        )
    )


def _action_update(task_id, title, description, labels, spec,
                   agent_model, judge, isolation, milestone_id, workplan_id="",
                   acceptance_criteria="", requires="", needs_review_before_start="",
                   needs_review_on_completion="", test_command=""):
    """Update mutable task fields."""
    if not task_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot update task: 'task_id' is required. "
                    "Use vtf_search_tasks to find the task you want to update."
                ),
                data={},
                available_actions=["vtf_search_tasks"],
            )
        )

    task, err = _get_task(task_id)
    if err:
        return err

    update_fields = ["updated_at"]

    if title:
        task.title = title
        update_fields.append("title")
    if description:
        task.description = description
        update_fields.append("description")
    if labels:
        task.labels = [lbl.strip() for lbl in labels.split(",") if lbl.strip()]
        update_fields.append("labels")
    if spec:
        task.spec = spec
        update_fields.append("spec")
    if agent_model:
        task.agent_model = agent_model
        update_fields.append("agent_model")
    if judge:
        task.judge = judge.lower() in ("true", "1", "yes")
        update_fields.append("judge")
    if isolation:
        task.isolation = isolation
        update_fields.append("isolation")
    if milestone_id:
        from workplans.models import Milestone

        try:
            milestone = Milestone.objects.get(pk=milestone_id)
            task.milestone = milestone
            task.workplan = milestone.workplan
            update_fields.extend(["milestone", "workplan"])
        except Milestone.DoesNotExist:
            pass

    if workplan_id:
        from workplans.models import Workplan
        try:
            workplan = Workplan.objects.get(pk=workplan_id)
            task.workplan = workplan
            if "workplan" not in update_fields:
                update_fields.append("workplan")
            # If task has a milestone from a different workplan, clear it
            if task.milestone and task.milestone.workplan_id != workplan.id:
                task.milestone = None
                if "milestone" not in update_fields:
                    update_fields.append("milestone")
        except Workplan.DoesNotExist:
            pass

    # acceptance_criteria — JSON array or comma-separated string
    if acceptance_criteria:
        try:
            task.acceptance_criteria = json.loads(acceptance_criteria)
        except json.JSONDecodeError:
            task.acceptance_criteria = [c.strip() for c in acceptance_criteria.split(",") if c.strip()]
        update_fields.append("acceptance_criteria")

    # requires — comma-separated task IDs, validate they exist
    if requires:
        req_ids = [r.strip() for r in requires.split(",") if r.strip()]
        existing = set(Task.objects.filter(pk__in=req_ids).values_list("pk", flat=True))
        missing = set(req_ids) - existing
        if missing:
            return json.dumps(error_response(
                message=f"Required task(s) not found: {', '.join(missing)}",
                data={"missing_ids": list(missing)},
                available_actions=["vtf_search_tasks"],
            ))
        task.requires = req_ids
        update_fields.append("requires")

    # needs_review_before_start
    if needs_review_before_start:
        task.needs_review_before_start = needs_review_before_start.lower() in ("true", "1", "yes")
        update_fields.append("needs_review_before_start")

    # needs_review_on_completion
    if needs_review_on_completion:
        task.needs_review_on_completion = needs_review_on_completion.lower() in ("true", "1", "yes")
        update_fields.append("needs_review_on_completion")

    # test_command — JSON dict
    if test_command:
        try:
            task.test_command = json.loads(test_command)
        except json.JSONDecodeError:
            return json.dumps(error_response(
                message="test_command must be valid JSON (e.g. '{\"unit\": \"pytest tests/...\"}').",
                data={},
                available_actions=["vtf_manage_task"],
            ))
        update_fields.append("test_command")

    task.save(update_fields=update_fields)

    return json.dumps(
        success_response(
            data={
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                }
            },
            message=f"Task {task.id} updated.",
            available_actions=["vtf_task_detail", "vtf_manage_task"],
        )
    )


def _action_transition(task_id, target_status, action_name):
    """Perform a simple state transition with no extra side effects."""
    if not task_id:
        return json.dumps(
            error_response(
                message=(
                    f"Cannot {action_name} task: 'task_id' is required. "
                    "Use vtf_search_tasks to find the task you want to transition."
                ),
                data={},
                available_actions=["vtf_search_tasks"],
            )
        )

    task, err = _get_task(task_id)
    if err:
        return err

    previous_status = task.status

    try:
        perform_transition(task, target_status)
    except InvalidTransition:
        valid = get_valid_transitions(task.status)
        return json.dumps(
            error_response(
                message=(
                    f"Cannot {action_name} task {task_id}: "
                    f"current status is '{task.status}'. "
                    f"Valid transitions: {valid}."
                ),
                data={
                    "task_id": task_id,
                    "current_status": task.status,
                    "valid_transitions": valid,
                },
                available_actions=["vtf_manage_task"],
            )
        )

    task.refresh_from_db()

    return json.dumps(
        success_response(
            data={
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "previous_status": previous_status,
                    "status": task.status,
                }
            },
            message=f"Task {task.id} {action_name} (was '{previous_status}').",
            available_actions=["vtf_task_detail", "vtf_board_overview"],
        )
    )


def _action_block(task_id, reason):
    """Transition task to blocked, recording reason as an event."""
    if not task_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot block task: 'task_id' is required. "
                    "Use vtf_search_tasks to find the task you want to block."
                ),
                data={},
                available_actions=["vtf_search_tasks"],
            )
        )

    task, err = _get_task(task_id)
    if err:
        return err

    previous_status = task.status

    try:
        perform_transition(task, "blocked")
    except InvalidTransition:
        valid = get_valid_transitions(task.status)
        return json.dumps(
            error_response(
                message=(
                    f"Cannot block task {task_id}: "
                    f"current status is '{task.status}' (terminal). "
                    "Terminal tasks cannot be transitioned. "
                    "Use 'reset' with admin privileges to force a state change."
                )
                if not valid
                else (
                    f"Cannot block task {task_id}: "
                    f"current status is '{task.status}'. "
                    f"Valid transitions: {valid}."
                ),
                data={
                    "task_id": task_id,
                    "current_status": task.status,
                    "valid_transitions": valid,
                },
                available_actions=["vtf_manage_task(action=reset)"],
            )
        )

    # Record reason event if provided
    if reason:
        record_event(
            task,
            "blocked_reason",
            data={"reason": reason},
            triggered_by="",
        )

    task.refresh_from_db()

    return json.dumps(
        success_response(
            data={
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "previous_status": previous_status,
                    "status": task.status,
                }
            },
            message=(
                f"Task {task.id} blocked (was '{previous_status}'). "
                "Use unblock when the blocker is resolved."
            ),
            available_actions=[
                "vtf_manage_task(action=unblock)",
                "vtf_board_overview",
            ],
        )
    )


def _action_delete(task_id):
    """Delete a task from the database."""
    if not task_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot delete task: 'task_id' is required. "
                    "Use vtf_search_tasks to find the task you want to delete."
                ),
                data={},
                available_actions=["vtf_search_tasks"],
            )
        )

    task, err = _get_task(task_id)
    if err:
        return err

    task_title = task.title
    task.delete()

    return json.dumps(
        success_response(
            data={"task_id": task_id, "title": task_title},
            message=f"Task {task_id} deleted.",
            available_actions=["vtf_board_overview"],
        )
    )


def _action_assign(task_id, assigned_to):
    """Set the assigned_to field on a task."""
    if not task_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot assign task: 'task_id' is required. "
                    "Use vtf_search_tasks to find the task you want to assign."
                ),
                data={},
                available_actions=["vtf_search_tasks"],
            )
        )
    if not assigned_to:
        return json.dumps(
            error_response(
                message=(
                    "Cannot assign task: 'assigned_to' is required. "
                    "Provide the agent or user ID to assign this task to."
                ),
                data={"task_id": task_id},
                available_actions=["vtf_manage_task(action=assign)"],
            )
        )

    task, err = _get_task(task_id)
    if err:
        return err

    task.assigned_to = assigned_to
    task.save(update_fields=["assigned_to", "updated_at"])

    return json.dumps(
        success_response(
            data={
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "assigned_to": task.assigned_to,
                }
            },
            message=f"Task {task.id} assigned to '{assigned_to}'.",
            available_actions=["vtf_task_detail"],
        )
    )


def _action_unassign(task_id):
    """Clear the assigned_to field on a task."""
    if not task_id:
        return json.dumps(
            error_response(
                message=(
                    "Cannot unassign task: 'task_id' is required. "
                    "Use vtf_search_tasks to find the task you want to unassign."
                ),
                data={},
                available_actions=["vtf_search_tasks"],
            )
        )

    task, err = _get_task(task_id)
    if err:
        return err

    task.assigned_to = None
    task.save(update_fields=["assigned_to", "updated_at"])

    return json.dumps(
        success_response(
            data={
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "assigned_to": task.assigned_to,
                }
            },
            message=f"Task {task.id} unassigned.",
            available_actions=["vtf_task_detail"],
        )
    )
