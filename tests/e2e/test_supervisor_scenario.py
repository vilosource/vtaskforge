"""
E2E supervisor agent scenario test.

Exercises the full supervisor review workflow over the real MCP HTTP transport
against the isolated docker compose stack, with every state transition
verified independently via the REST API.

Workflow: board_overview -> search_tasks -> task_detail -> review_task (approve)

Requires the E2E stack to be running and seeded:
    docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python src/manage.py migrate --run-syncdb
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python -c "exec(open('/app/tests/e2e/seed.py').read())"
"""
import asyncio

from tests.e2e.mcp_client import McpTestClient


def test_supervisor_review_workflow(e2e_mcp_url, auth_token, rest_client):
    """Supervisor: board -> search -> detail -> review, verified via REST."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Step 1: board_overview — check pending reviews
            # ------------------------------------------------------------------
            r = await mcp.call_tool("vtf_board_overview", project_id="e2e-project")
            assert r["success"] is True, f"vtf_board_overview failed: {r}"

            # ------------------------------------------------------------------
            # Step 2: search pending_completion_review tasks
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_search_tasks",
                status="pending_completion_review",
                project_id="e2e-project",
            )
            assert r["success"] is True, f"vtf_search_tasks failed: {r}"
            assert r["data"]["total_count"] >= 1, (
                f"Expected at least 1 pending_completion_review task, got: {r['data']['total_count']}"
            )
            task_id = r["data"]["tasks"][0]["id"]
            assert task_id, "search returned a task with no id"

            # ------------------------------------------------------------------
            # Step 3: task_detail — inspect the task
            # ------------------------------------------------------------------
            r = await mcp.call_tool("vtf_task_detail", task_id=task_id)
            assert r["success"] is True, f"vtf_task_detail failed: {r}"
            assert r["data"]["task"]["status"] == "pending_completion_review", (
                f"Expected status=pending_completion_review, got: {r['data']['task']['status']}"
            )

            # ------------------------------------------------------------------
            # Step 4: review_task — approve the task
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_review_task",
                task_id=task_id,
                decision="approved",
                reviewer_id="e2e-supervisor",
            )
            assert r["success"] is True, f"vtf_review_task failed: {r}"
            assert r["data"]["task"]["status"] == "done", (
                f"Expected status=done after approval, got: {r['data']['task']['status']}"
            )

            # REST verify — independent channel confirms the DB state
            task = rest_client.get_task(task_id)
            assert task is not None, f"Task {task_id} not found via REST after review"
            assert task["status"] == "done", (
                f"REST: expected status=done after approval, got: {task['status']}"
            )

    asyncio.run(run())
