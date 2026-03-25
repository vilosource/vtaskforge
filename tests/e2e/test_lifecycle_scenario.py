"""
E2E full task lifecycle scenario tests.

Exercises the complete task lifecycle using vtf_manage_task plus executor
workflow tools. Every state transition is verified independently via the
REST API.

Workflow 1: create -> submit -> claim -> progress -> submit_work -> (review) -> delete
Workflow 2: create -> submit -> block -> unblock -> cancel -> delete

Requires the E2E stack to be running and seeded:
    docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python src/manage.py migrate --run-syncdb
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python -c "exec(open('/app/tests/e2e/seed.py').read())"
"""
import asyncio

from tests.e2e.mcp_client import McpTestClient


def test_full_task_lifecycle(e2e_mcp_url, auth_token, rest_client):
    """Create -> submit -> claim -> progress -> submit_work -> review -> delete."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Step 1: create — new task in draft status
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="create",
                title="Lifecycle E2E",
                project_id="e2e-project",
            )
            assert r["success"] is True, f"vtf_manage_task(create) failed: {r}"
            task_id = r["data"]["task"]["id"]
            assert task_id, "create returned a task with no id"
            assert r["data"]["task"]["status"] == "draft", (
                f"Expected status=draft after create, got: {r['data']['task']['status']}"
            )

            # REST verify
            task = rest_client.get_task(task_id)
            assert task is not None, f"Task {task_id} not found via REST after create"
            assert task["status"] == "draft", (
                f"REST: expected status=draft after create, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 2: submit — draft -> todo
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="submit", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(submit) failed: {r}"
            assert r["data"]["task"]["status"] == "todo", (
                f"Expected status=todo after submit, got: {r['data']['task']['status']}"
            )

            # REST verify
            task = rest_client.get_task(task_id)
            assert task["status"] == "todo", (
                f"REST: expected status=todo after submit, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 3: claim_and_start — todo -> doing
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_claim_and_start", task_id=task_id, agent_id="e2e-executor"
            )
            assert r["success"] is True, f"vtf_claim_and_start failed: {r}"
            assert r["data"]["task"]["status"] == "doing", (
                f"Expected status=doing after claim, got: {r['data']['task']['status']}"
            )

            # REST verify
            task = rest_client.get_task(task_id)
            assert task is not None, f"Task {task_id} not found via REST after claim"
            assert task["status"] == "doing", (
                f"REST: expected status=doing after claim, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 4: report_progress — note partial work
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_report_progress", task_id=task_id, note="working"
            )
            assert r["data"]["note_added"] is True, (
                f"Expected note_added=True in report_progress response, got: {r}"
            )

            # ------------------------------------------------------------------
            # Step 5: submit_work — doing -> done or pending_completion_review
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_submit_work", task_id=task_id, completion_note="done"
            )
            assert r["success"] is True, f"vtf_submit_work failed: {r}"
            status = r["data"]["task"]["status"]
            assert status in ("done", "pending_completion_review"), (
                f"Unexpected final status after submit_work: {status}"
            )

            # REST verify
            task = rest_client.get_task(task_id)
            assert task is not None, f"Task {task_id} not found via REST after submit_work"
            assert task["status"] == status, (
                f"REST: expected status={status}, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 6: review if needed — pending_completion_review -> done
            # ------------------------------------------------------------------
            if status == "pending_completion_review":
                r = await mcp.call_tool(
                    "vtf_review_task",
                    task_id=task_id,
                    decision="approved",
                    reviewer_id="e2e-supervisor",
                )
                assert r["success"] is True, f"vtf_review_task failed: {r}"
                assert r["data"]["task"]["status"] == "done", (
                    f"Expected status=done after review approval, "
                    f"got: {r['data']['task']['status']}"
                )

                # REST verify
                task = rest_client.get_task(task_id)
                assert task is not None, f"Task {task_id} not found via REST after review"
                assert task["status"] == "done", (
                    f"REST: expected status=done after review, got: {task['status']}"
                )

            # ------------------------------------------------------------------
            # Step 7: delete — remove task from database
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="delete", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(delete) failed: {r}"

            # REST verify — task should be gone
            task = rest_client.get_task(task_id)
            assert task is None, (
                f"Expected task {task_id} to be deleted, but REST still returns it"
            )

    asyncio.run(run())


def test_manage_block_unblock_cycle(e2e_mcp_url, auth_token, rest_client):
    """Create -> submit -> block -> unblock -> cancel -> delete."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Step 1: create — new task in draft status
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="create",
                title="Block E2E",
                project_id="e2e-project",
            )
            assert r["success"] is True, f"vtf_manage_task(create) failed: {r}"
            task_id = r["data"]["task"]["id"]
            assert task_id, "create returned a task with no id"

            # ------------------------------------------------------------------
            # Step 2: submit — draft -> todo
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="submit", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(submit) failed: {r}"

            # REST verify
            task = rest_client.get_task(task_id)
            assert task["status"] == "todo", (
                f"REST: expected status=todo after submit, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 3: block — todo -> blocked
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="block", task_id=task_id, reason="dependency"
            )
            assert r["success"] is True, f"vtf_manage_task(block) failed: {r}"
            assert r["data"]["task"]["status"] == "blocked", (
                f"Expected status=blocked after block, got: {r['data']['task']['status']}"
            )

            # REST verify
            task = rest_client.get_task(task_id)
            assert task["status"] == "blocked", (
                f"REST: expected status=blocked after block, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 4: unblock — blocked -> todo
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="unblock", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(unblock) failed: {r}"
            assert r["data"]["task"]["status"] == "todo", (
                f"Expected status=todo after unblock, got: {r['data']['task']['status']}"
            )

            # REST verify
            task = rest_client.get_task(task_id)
            assert task["status"] == "todo", (
                f"REST: expected status=todo after unblock, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 5: cancel — todo -> cancelled
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="cancel", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(cancel) failed: {r}"
            assert r["data"]["task"]["status"] == "cancelled", (
                f"Expected status=cancelled after cancel, "
                f"got: {r['data']['task']['status']}"
            )

            # REST verify
            task = rest_client.get_task(task_id)
            assert task["status"] == "cancelled", (
                f"REST: expected status=cancelled after cancel, got: {task['status']}"
            )

            # ------------------------------------------------------------------
            # Step 6: delete — remove task from database
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="delete", task_id=task_id
            )
            assert r["success"] is True, f"vtf_manage_task(delete) failed: {r}"

            # REST verify — task should be gone
            task = rest_client.get_task(task_id)
            assert task is None, (
                f"Expected task {task_id} to be deleted, but REST still returns it"
            )

    asyncio.run(run())
