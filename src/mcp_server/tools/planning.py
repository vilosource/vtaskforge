"""
MCP tool: vtf_plan_work

Batch-creates a workplan with tasks in one call. Replaces the multi-step
pattern of create_workplan → create_task × N → submit_task × N.
"""

import json

from mcp_server.project_context import get_default_project
from mcp_server.responses import error_response, success_response
from mcp_server.server import mcp
from mcp_server.utils import parse_test_command as _parse_test_command
from projects.models import Project
from tasks.exceptions import GuardViolation, InvalidTransition
from tasks.models import Task
from tasks.state_machine import perform_transition
from workplans.models import Workplan


@mcp.tool()
def vtf_plan_work(
    workplan_name: str,
    tasks: str,
    project_id: str = "",
    description: str = "",
) -> str:
    """Plan work by creating a workplan with tasks in one call.

    Creates the workplan, creates all tasks, and submits them to 'todo' status.
    test_command can be a plain string (e.g. "pytest tests/") or JSON object.

    Args:
        workplan_name: Name for the new workplan
        tasks: JSON array of task objects, each with 'title' and 'spec'.
               Optional: 'test_command', 'labels', 'description',
               'acceptance_criteria'.
        project_id: Project ID (defaults to session project from X-VTF-Project)
        description: Optional workplan description

    Example tasks JSON:
    [
      {"title": "Add auth endpoint", "spec": "Implement OAuth2 login",
       "test_command": "pytest tests/test_auth.py"},
      {"title": "Add rate limiting", "spec": "Add middleware"}
    ]
    """
    # Resolve project
    pid = project_id or get_default_project()
    if not pid:
        return json.dumps(error_response(
            message="No project specified. Provide project_id or ensure X-VTF-Project header is set.",
            available_actions=["vtf_get_context"],
        ))

    # Verify project exists
    try:
        project = Project.objects.get(pk=pid)
    except Project.DoesNotExist:
        return json.dumps(error_response(
            message=f"Project '{pid}' not found.",
            available_actions=["vtf_get_context"],
        ))

    # Parse tasks JSON
    try:
        task_defs = json.loads(tasks)
    except json.JSONDecodeError:
        return json.dumps(error_response(
            message="Invalid tasks JSON. Provide a JSON array of task objects.",
            available_actions=["vtf_plan_work"],
        ))

    if not isinstance(task_defs, list) or not task_defs:
        return json.dumps(error_response(
            message="tasks must be a non-empty JSON array.",
            available_actions=["vtf_plan_work"],
        ))

    # Create workplan
    workplan = Workplan.objects.create(
        name=workplan_name,
        project=project,
        description=description,
        status="active",
    )

    # Create and submit tasks
    created_tasks = []
    errors = []

    for i, td in enumerate(task_defs):
        title = td.get("title", f"Task {i + 1}")
        spec = td.get("spec", "")

        kwargs = {
            "title": title,
            "spec": spec,
            "project": project,
            "workplan": workplan,
            "status": "draft",
        }

        # Parse test_command (accepts plain string or JSON)
        raw_tc = td.get("test_command", "")
        if raw_tc:
            parsed_tc = _parse_test_command(str(raw_tc))
            if parsed_tc:
                kwargs["test_command"] = parsed_tc

        # Optional fields
        if td.get("labels"):
            labels = td["labels"]
            if isinstance(labels, str):
                kwargs["labels"] = [l.strip() for l in labels.split(",")]
            elif isinstance(labels, list):
                kwargs["labels"] = labels

        if td.get("description"):
            kwargs["description"] = td["description"]

        if td.get("acceptance_criteria"):
            ac = td["acceptance_criteria"]
            if isinstance(ac, list):
                kwargs["acceptance_criteria"] = ac

        task = Task.objects.create(**kwargs)

        # Submit (draft → todo)
        try:
            perform_transition(task, "todo")
            from mcp_server.serialization import serialize_task
            created_tasks.append(serialize_task(task))
        except (InvalidTransition, GuardViolation) as e:
            errors.append({
                "task": serialize_task(task),
                "error": str(e),
            })

    from mcp_server.serialization import serialize_workplan
    data = {
        "workplan": serialize_workplan(workplan),
        "tasks": created_tasks,
        "errors": errors,
    }

    if errors:
        message = (
            f"Created workplan '{workplan_name}' with {len(created_tasks)} tasks submitted, "
            f"{len(errors)} task(s) could not be submitted."
        )
    else:
        message = (
            f"Created workplan '{workplan_name}' with {len(created_tasks)} tasks, "
            f"all submitted to todo."
        )

    return json.dumps(success_response(
        data=data,
        message=message,
        available_actions=["vtf_get_context", "vtf_task_detail"],
    ))
