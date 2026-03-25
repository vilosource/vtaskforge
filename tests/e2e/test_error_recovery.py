"""
E2E error recovery scenario tests.

Exercises error paths: invalid actions, wrong task state, auth failures.
Verifies that error responses are actionable and available_actions guide
recovery.

Requires the E2E stack to be running and seeded:
    docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python src/manage.py migrate --run-syncdb
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python -c "exec(open('/app/tests/e2e/seed.py').read())"
"""
import asyncio

import httpx

from tests.e2e.conftest import E2E_MCP_URL
from tests.e2e.mcp_client import McpTestClient


def test_claim_nonexistent_task(e2e_mcp_url, auth_token):
    """Claiming a nonexistent task returns actionable error."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            r = await mcp.call_tool(
                "vtf_claim_and_start",
                task_id="does-not-exist",
                agent_id="e2e-executor",
            )
            assert r["success"] is False, (
                f"Expected success=False when claiming nonexistent task, got: {r}"
            )
            actions = r.get("available_actions", [])
            assert actions, (
                f"Expected non-empty available_actions for nonexistent task error, got: {r}"
            )

    asyncio.run(run())


def test_submit_work_on_todo_task(e2e_mcp_url, auth_token, rest_client):
    """Submitting work on a non-doing task returns actionable error."""
    task_id = None

    async def run():
        nonlocal task_id
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # Create a task and submit it to todo (not doing)
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="create",
                title="Error Recovery: Submit on Todo",
                project_id="e2e-project",
            )
            assert r["success"] is True, f"vtf_manage_task(create) failed: {r}"
            task_id = r["data"]["task"]["id"]

            r = await mcp.call_tool(
                "vtf_manage_task", action="submit", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(submit) failed: {r}"
            assert r["data"]["task"]["status"] == "todo", (
                f"Expected status=todo after submit, got: {r['data']['task']['status']}"
            )

            # Attempt vtf_submit_work on a todo task — should fail
            r = await mcp.call_tool(
                "vtf_submit_work",
                task_id=task_id,
                completion_note="premature completion",
            )
            assert r["success"] is False, (
                f"Expected success=False when submitting work on todo task, got: {r}"
            )
            message = r.get("message", "")
            assert "doing" in message.lower(), (
                f"Expected 'doing' in error message, got: {message!r}"
            )
            actions = r.get("available_actions", [])
            assert actions, (
                f"Expected non-empty available_actions for wrong-state error, got: {r}"
            )

            # Cleanup: delete the task
            r = await mcp.call_tool(
                "vtf_manage_task", action="delete", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(delete) failed: {r}"
            task_id = None

    asyncio.run(run())

    # Failsafe REST cleanup if the async block failed before the delete step
    if task_id is not None:
        rest_client.client.delete(f"/tasks/{task_id}/")


def test_review_non_review_task(e2e_mcp_url, auth_token, rest_client):
    """Reviewing a draft task returns actionable error."""
    task_id = None

    async def run():
        nonlocal task_id
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # Create a draft task (do NOT submit — keep it in draft)
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="create",
                title="Error Recovery: Review Draft",
                project_id="e2e-project",
            )
            assert r["success"] is True, f"vtf_manage_task(create) failed: {r}"
            task_id = r["data"]["task"]["id"]
            assert r["data"]["task"]["status"] == "draft", (
                f"Expected status=draft after create, got: {r['data']['task']['status']}"
            )

            # Attempt vtf_review_task on a draft task — should fail
            r = await mcp.call_tool(
                "vtf_review_task",
                task_id=task_id,
                decision="approved",
                reviewer_id="e2e-supervisor",
            )
            assert r["success"] is False, (
                f"Expected success=False when reviewing a draft task, got: {r}"
            )
            actions = r.get("available_actions", [])
            assert actions, (
                f"Expected non-empty available_actions for wrong-state review error, got: {r}"
            )

            # Cleanup: delete the task
            r = await mcp.call_tool(
                "vtf_manage_task", action="delete", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(delete) failed: {r}"
            task_id = None

    asyncio.run(run())

    # Failsafe REST cleanup if the async block failed before the delete step
    if task_id is not None:
        rest_client.client.delete(f"/tasks/{task_id}/")


def test_invalid_manage_action(e2e_mcp_url, auth_token):
    """Unknown manage action returns error with valid actions listed."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            r = await mcp.call_tool("vtf_manage_task", action="explode")
            assert r["success"] is False, (
                f"Expected success=False for unknown action 'explode', got: {r}"
            )
            message = r.get("message", "")
            assert "valid" in message.lower() or "unknown" in message.lower(), (
                f"Expected 'valid' or 'unknown' in error message, got: {message!r}"
            )

    asyncio.run(run())


def test_auth_rejected_without_token():
    """HTTP request without auth gets 401."""
    r = httpx.post(
        E2E_MCP_URL,
        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
        headers={"Content-Type": "application/json"},
        timeout=10.0,
    )
    assert r.status_code == 401, (
        f"Expected 401 for unauthenticated request, got: {r.status_code}"
    )
