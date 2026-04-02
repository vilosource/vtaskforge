"""
E2E smoke tests — verify the stack is healthy and basic connectivity works.

Requires the E2E stack to be running and seeded:
    docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python src/manage.py migrate --run-syncdb
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python -c "exec(open('/app/tests/e2e/seed.py').read())"
"""
import asyncio

import pytest

from tests.e2e.mcp_client import McpTestClient


EXPECTED_TOOLS = [
    "vtf_board_overview",
    "vtf_claim_and_start",
    "vtf_list_members",
    "vtf_manage_channel_mapping",
    "vtf_manage_lock",
    "vtf_manage_milestone",
    "vtf_manage_task",
    "vtf_manage_workplan",
    "vtf_next_work",
    "vtf_report_progress",
    "vtf_resolve_channel",
    "vtf_review_task",
    "vtf_search_tasks",
    "vtf_submit_work",
    "vtf_task_detail",
    "vtf_whoami",
    "vtf_workplan_tree",
]


def test_e2e_stack_is_healthy(mcp_tools, rest_client):
    """Verify that the MCP server exposes all expected tools and the REST API responds."""
    # MCP server
    assert len(mcp_tools) == len(EXPECTED_TOOLS), (
        f"Expected {len(EXPECTED_TOOLS)} tools, got {len(mcp_tools)}: {mcp_tools}"
    )
    for name in EXPECTED_TOOLS:
        assert name in mcp_tools, f"Tool '{name}' not found in {mcp_tools}"

    # REST API responds with a list of tasks (seeded data)
    tasks = rest_client.list_tasks()
    assert isinstance(tasks, list), f"Expected list, got {type(tasks)}"


def test_rest_api_responds(rest_client):
    """REST API responds to authenticated requests with task data."""
    # Use the tasks endpoint — fast and doesn't depend on Redis.
    tasks = rest_client.list_tasks()
    assert isinstance(tasks, list)
    # Seeded data should be present
    assert len(tasks) >= 5, f"Expected at least 5 seeded tasks, got {len(tasks)}"


def test_rest_api_seeded_project(rest_client):
    """Seeded project exists and is accessible."""
    project = rest_client.get_project("e2e-project")
    assert project is not None, "Seeded project 'e2e-project' not found"
    assert project["name"] == "E2E Test Project"


def test_rest_api_seeded_tasks(rest_client):
    """Seeded tasks exist with expected statuses."""
    todo_tasks = rest_client.list_tasks(status="todo")
    assert len(todo_tasks) >= 2, f"Expected at least 2 todo tasks, got {len(todo_tasks)}"

    task = rest_client.get_task("e2e-todo-1")
    assert task is not None, "Seeded task 'e2e-todo-1' not found"
    assert task["status"] == "todo"

    review_task = rest_client.get_task("e2e-review")
    assert review_task is not None, "Seeded task 'e2e-review' not found"
    assert review_task["status"] == "pending_completion_review"


def test_mcp_board_overview(e2e_mcp_url, auth_token):
    """MCP vtf_board_overview tool returns a successful response."""

    async def run():
        async with McpTestClient(url=e2e_mcp_url, token=auth_token) as client:
            result = await client.call_tool("vtf_board_overview")
            return result

    data = asyncio.run(run())
    assert data["success"] is True, f"Expected success=True, got: {data}"
    assert "data" in data
