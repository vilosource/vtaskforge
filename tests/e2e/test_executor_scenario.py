"""
E2E executor agent scenario test.

Exercises the full executor agent workflow over the real MCP HTTP transport
against the isolated docker compose stack, with every state transition
verified independently via the REST API.

Workflow: next_work -> claim_and_start -> report_progress -> submit_work

Requires the E2E stack to be running and seeded:
    docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python src/manage.py migrate --run-syncdb
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python -c "exec(open('/app/tests/e2e/seed.py').read())"
"""
import asyncio

from tests.e2e.mcp_client import McpTestClient


def test_executor_find_and_complete_task(e2e_mcp_url, auth_token, rest_client):
    """Executor: next_work -> claim -> progress -> submit_work, verified via REST."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Step 1: next_work — find a claimable task in the e2e-project
            # ------------------------------------------------------------------
            r = await mcp.call_tool("vtf_next_work", project_id="e2e-project")
            assert r["success"] is True, f"vtf_next_work failed: {r}"
            task_id = r["data"]["task"]["id"]
            assert task_id, "next_work returned a task with no id"

            # available_actions should suggest claiming the task
            actions = r.get("available_actions", [])
            assert any("claim" in a for a in actions), (
                f"Expected 'claim' in available_actions, got: {actions}"
            )

            # ------------------------------------------------------------------
            # Step 2: claim_and_start — claim the task as e2e-executor
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_claim_and_start", task_id=task_id, agent_id="e2e-executor"
            )
            assert r["success"] is True, f"vtf_claim_and_start failed: {r}"
            assert r["data"]["task"]["status"] == "doing", (
                f"Expected status=doing after claim, got: {r['data']['task']['status']}"
            )

            # REST verify — independent channel confirms the DB state
            task = rest_client.get_task(task_id)
            assert task is not None, f"Task {task_id} not found via REST after claim"
            assert task["status"] == "doing", (
                f"REST: expected status=doing, got: {task['status']}"
            )
            assert task["claimed_by"] == "e2e-executor", (
                f"REST: expected claimed_by=e2e-executor, got: {task['claimed_by']}"
            )

            # ------------------------------------------------------------------
            # Step 3: report_progress — signal partial completion
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_report_progress", task_id=task_id, note="halfway done"
            )
            assert r["data"]["note_added"] is True, (
                f"Expected note_added=True in report_progress response, got: {r}"
            )

            # available_actions after progress should suggest submitting
            actions = r.get("available_actions", [])
            assert any("submit" in a for a in actions), (
                f"Expected 'submit' in available_actions after progress, got: {actions}"
            )

            # ------------------------------------------------------------------
            # Step 4: submit_work — complete the task
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_submit_work", task_id=task_id, completion_note="all done"
            )
            assert r["success"] is True, f"vtf_submit_work failed: {r}"
            final_status = r["data"]["task"]["status"]
            assert final_status in ("done", "pending_completion_review"), (
                f"Unexpected final status after submit: {final_status}"
            )

            # REST verify — independent channel confirms final status
            task = rest_client.get_task(task_id)
            assert task is not None, f"Task {task_id} not found via REST after submit"
            assert task["status"] == final_status, (
                f"REST: expected status={final_status}, got: {task['status']}"
            )

    asyncio.run(run())
