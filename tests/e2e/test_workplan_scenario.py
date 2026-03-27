"""
E2E workplan and milestone scenario tests.

Exercises vtf_manage_workplan, vtf_manage_milestone, and vtf_workplan_tree
tools with dual-channel verification via the REST API.

Workflow 1: Workplan CRUD — create, list, update, tree view, complete, archive
Workflow 2: Milestone lifecycle — create, list, activate, add tasks, complete, delete
Workflow 3: Task note action and new task params (acceptance_criteria, requires, test_command)
Workflow 4: Reviewer != claimer enforcement

Requires the E2E stack to be running and seeded:
    docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python src/manage.py migrate --run-syncdb
    docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api \\
        python -c "exec(open('/app/tests/e2e/seed.py').read())"
"""
import asyncio

from tests.e2e.mcp_client import McpTestClient


def test_workplan_crud_lifecycle(e2e_mcp_url, auth_token, rest_client):
    """Create -> list -> update -> tree -> complete workplan."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Step 1: create workplan
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_workplan",
                action="create",
                name="E2E Workplan Test",
                project_id="e2e-project",
            )
            assert r["success"] is True, f"create workplan failed: {r}"
            wp_id = r["data"]["workplan"]["id"]
            assert wp_id, "create returned workplan with no id"
            assert r["data"]["workplan"]["status"] == "active"

            # REST verify
            wp = rest_client.get_workplan(wp_id)
            assert wp is not None, f"Workplan {wp_id} not found via REST"

            # ------------------------------------------------------------------
            # Step 2: list workplans — should include the new one
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_workplan",
                action="list",
                project_id="e2e-project",
            )
            assert r["success"] is True, f"list workplans failed: {r}"
            wp_ids = [w["id"] for w in r["data"]["workplans"]]
            assert wp_id in wp_ids, f"New workplan {wp_id} not in list: {wp_ids}"

            # ------------------------------------------------------------------
            # Step 3: update workplan name
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_workplan",
                action="update",
                workplan_id=wp_id,
                name="E2E Workplan Updated",
                description="Updated description",
            )
            assert r["success"] is True, f"update workplan failed: {r}"

            # REST verify
            wp = rest_client.get_workplan(wp_id)
            assert wp["name"] == "E2E Workplan Updated"

            # ------------------------------------------------------------------
            # Step 4: workplan tree — empty at this point
            # ------------------------------------------------------------------
            r = await mcp.call_tool("vtf_workplan_tree", workplan_id=wp_id)
            assert r["success"] is True, f"workplan_tree failed: {r}"
            assert "milestones" in r["data"]

            # ------------------------------------------------------------------
            # Step 5: complete workplan
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_workplan",
                action="complete",
                workplan_id=wp_id,
            )
            assert r["success"] is True, f"complete workplan failed: {r}"

            # REST verify
            wp = rest_client.get_workplan(wp_id)
            assert wp["status"] == "completed", (
                f"Expected status=completed, got: {wp['status']}"
            )

            # ------------------------------------------------------------------
            # Step 6: archive workplan
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_workplan",
                action="archive",
                workplan_id=wp_id,
            )
            assert r["success"] is True, f"archive workplan failed: {r}"

            # REST verify
            wp = rest_client.get_workplan(wp_id)
            assert wp["status"] == "archived", (
                f"Expected status=archived, got: {wp['status']}"
            )

    asyncio.run(run())


def test_milestone_lifecycle_with_tasks(e2e_mcp_url, auth_token, rest_client):
    """Create workplan -> create milestones -> activate -> add tasks -> tree -> complete -> delete."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Setup: create a workplan for this test
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_workplan",
                action="create",
                name="Milestone E2E Workplan",
                project_id="e2e-project",
            )
            assert r["success"] is True
            wp_id = r["data"]["workplan"]["id"]

            # ------------------------------------------------------------------
            # Step 1: create two milestones
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_milestone",
                action="create",
                workplan_id=wp_id,
                name="Milestone Alpha",
                order="0",
            )
            assert r["success"] is True, f"create milestone failed: {r}"
            ms1_id = r["data"]["milestone"]["id"]
            assert r["data"]["milestone"]["status"] == "pending"

            r = await mcp.call_tool(
                "vtf_manage_milestone",
                action="create",
                workplan_id=wp_id,
                name="Milestone Beta",
                order="1",
            )
            assert r["success"] is True
            ms2_id = r["data"]["milestone"]["id"]

            # REST verify
            ms1 = rest_client.get_milestone(ms1_id)
            assert ms1 is not None, f"Milestone {ms1_id} not found via REST"
            assert ms1["name"] == "Milestone Alpha"

            # ------------------------------------------------------------------
            # Step 2: list milestones
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_milestone",
                action="list",
                workplan_id=wp_id,
            )
            assert r["success"] is True
            ms_ids = [m["id"] for m in r["data"]["milestones"]]
            assert ms1_id in ms_ids
            assert ms2_id in ms_ids

            # ------------------------------------------------------------------
            # Step 3: update milestone name
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_milestone",
                action="update",
                milestone_id=ms1_id,
                name="Milestone Alpha Updated",
            )
            assert r["success"] is True

            # REST verify
            ms1 = rest_client.get_milestone(ms1_id)
            assert ms1["name"] == "Milestone Alpha Updated"

            # ------------------------------------------------------------------
            # Step 4: activate milestone
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_milestone",
                action="activate",
                milestone_id=ms1_id,
            )
            assert r["success"] is True
            assert r["data"]["milestone"]["status"] == "active"

            # REST verify
            ms1 = rest_client.get_milestone(ms1_id)
            assert ms1["status"] == "active"

            # ------------------------------------------------------------------
            # Step 5: create a task in the milestone
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="create",
                title="Milestone task",
                project_id="e2e-project",
                milestone_id=ms1_id,
                workplan_id=wp_id,
            )
            assert r["success"] is True
            task_id = r["data"]["task"]["id"]

            # ------------------------------------------------------------------
            # Step 6: workplan tree — should show milestone with task
            # ------------------------------------------------------------------
            r = await mcp.call_tool("vtf_workplan_tree", workplan_id=wp_id)
            assert r["success"] is True
            milestones = r["data"]["milestones"]
            ms1_in_tree = [m for m in milestones if m["id"] == ms1_id]
            assert len(ms1_in_tree) == 1, f"Milestone {ms1_id} not in tree"
            ms1_tasks = ms1_in_tree[0]["tasks"]
            task_ids_in_tree = [t["id"] for t in ms1_tasks]
            assert task_id in task_ids_in_tree, (
                f"Task {task_id} not in milestone tree: {task_ids_in_tree}"
            )

            # ------------------------------------------------------------------
            # Step 7: complete milestone
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_milestone",
                action="complete",
                milestone_id=ms1_id,
            )
            assert r["success"] is True
            assert r["data"]["milestone"]["status"] == "completed"

            # REST verify
            ms1 = rest_client.get_milestone(ms1_id)
            assert ms1["status"] == "completed"

            # ------------------------------------------------------------------
            # Step 8: delete second milestone
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_milestone",
                action="delete",
                milestone_id=ms2_id,
            )
            assert r["success"] is True

            # REST verify — should be gone
            ms2 = rest_client.get_milestone(ms2_id)
            assert ms2 is None, f"Milestone {ms2_id} should be deleted"

            # ------------------------------------------------------------------
            # Cleanup: delete the task and workplan
            # ------------------------------------------------------------------
            await mcp.call_tool(
                "vtf_manage_task", action="delete", task_id=task_id
            )

    asyncio.run(run())


def test_task_note_and_extended_params(e2e_mcp_url, auth_token, rest_client):
    """Test vtf_manage_task note action and new task params (acceptance_criteria, test_command)."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Step 1: create task with extended params
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="create",
                title="Extended Params E2E",
                project_id="e2e-project",
                description="Task with extended parameters",
                labels="e2e,test",
                acceptance_criteria="Tests pass,No regressions",
                test_command='{"unit": "pytest tests/"}',
            )
            assert r["success"] is True, f"create with extended params failed: {r}"
            task_id = r["data"]["task"]["id"]

            # REST verify params were stored
            task = rest_client.get_task(task_id)
            assert task is not None
            assert "e2e" in task.get("labels", [])

            # ------------------------------------------------------------------
            # Step 2: submit task
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task", action="submit", task_id=task_id
            )
            assert r["success"] is True

            # ------------------------------------------------------------------
            # Step 3: add a note (note action works on any status)
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="note",
                task_id=task_id,
                reason="Important context for this task",
            )
            assert r["success"] is True, f"note action failed: {r}"

            # ------------------------------------------------------------------
            # Step 4: verify note via task detail
            # ------------------------------------------------------------------
            r = await mcp.call_tool("vtf_task_detail", task_id=task_id)
            assert r["success"] is True
            notes = r["data"].get("notes", [])
            assert len(notes) >= 1, f"Expected at least 1 note, got: {notes}"

            # ------------------------------------------------------------------
            # Step 5: update with new fields
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="update",
                task_id=task_id,
                description="Updated description",
                labels="e2e,updated",
            )
            assert r["success"] is True

            # REST verify
            task = rest_client.get_task(task_id)
            assert "updated" in task.get("labels", [])

            # ------------------------------------------------------------------
            # Cleanup
            # ------------------------------------------------------------------
            await mcp.call_tool(
                "vtf_manage_task", action="delete", task_id=task_id
            )

    asyncio.run(run())


def test_reviewer_cannot_be_claimer(e2e_mcp_url, auth_token, rest_client):
    """Verify that vtf_review_task rejects reviews where reviewer_id == claimed_by."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # ------------------------------------------------------------------
            # Setup: create task with review required, claim it, submit work
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_manage_task",
                action="create",
                title="Self-review E2E",
                project_id="e2e-project",
                needs_review_on_completion="true",
            )
            assert r["success"] is True
            task_id = r["data"]["task"]["id"]

            await mcp.call_tool(
                "vtf_manage_task", action="submit", task_id=task_id
            )
            await mcp.call_tool(
                "vtf_claim_and_start", task_id=task_id, agent_id="e2e-executor"
            )
            r = await mcp.call_tool(
                "vtf_submit_work", task_id=task_id, completion_note="done"
            )
            assert r["success"] is True
            assert r["data"]["task"]["status"] == "pending_completion_review"

            # ------------------------------------------------------------------
            # Attempt self-review — should fail
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_review_task",
                task_id=task_id,
                decision="approved",
                reviewer_id="e2e-executor",
            )
            assert r["success"] is False, (
                f"Expected self-review to be rejected, got: {r}"
            )

            # ------------------------------------------------------------------
            # Independent review — should succeed
            # ------------------------------------------------------------------
            r = await mcp.call_tool(
                "vtf_review_task",
                task_id=task_id,
                decision="approved",
                reviewer_id="e2e-supervisor",
            )
            assert r["success"] is True, f"Independent review failed: {r}"
            assert r["data"]["task"]["status"] == "done"

            # REST verify
            task = rest_client.get_task(task_id)
            assert task["status"] == "done"

            # ------------------------------------------------------------------
            # Cleanup
            # ------------------------------------------------------------------
            await mcp.call_tool(
                "vtf_manage_task", action="delete", task_id=task_id
            )

    asyncio.run(run())


def test_workplan_tree_with_seeded_data(e2e_mcp_url, auth_token):
    """Verify vtf_workplan_tree returns hierarchy for the seeded workplan."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            r = await mcp.call_tool("vtf_workplan_tree", workplan_id="e2e-workplan")
            assert r["success"] is True, f"workplan_tree failed: {r}"
            assert r["data"]["workplan"]["id"] == "e2e-workplan"
            milestones = r["data"]["milestones"]
            assert len(milestones) >= 1, "Expected at least 1 milestone in seeded workplan"

            # The seeded milestone should have tasks
            ms = [m for m in milestones if m["id"] == "e2e-milestone"]
            assert len(ms) == 1, "Seeded milestone 'e2e-milestone' not in tree"
            assert len(ms[0]["tasks"]) >= 1, "Expected tasks in seeded milestone"

    asyncio.run(run())


def test_board_overview_with_workplan_filter(e2e_mcp_url, auth_token):
    """Verify vtf_board_overview accepts workplan_id filter."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            r = await mcp.call_tool(
                "vtf_board_overview", workplan_id="e2e-workplan"
            )
            assert r["success"] is True, f"board_overview with workplan_id failed: {r}"
            assert "data" in r

    asyncio.run(run())


def test_search_tasks_with_workplan_filter(e2e_mcp_url, auth_token):
    """Verify vtf_search_tasks accepts workplan_id and milestone_id filters."""

    async def run():
        async with McpTestClient(e2e_mcp_url, auth_token) as mcp:
            # Filter by workplan
            r = await mcp.call_tool(
                "vtf_search_tasks", workplan_id="e2e-workplan"
            )
            assert r["success"] is True, f"search with workplan_id failed: {r}"
            assert r["data"]["total_count"] >= 1

            # Filter by milestone
            r = await mcp.call_tool(
                "vtf_search_tasks", milestone_id="e2e-milestone"
            )
            assert r["success"] is True, f"search with milestone_id failed: {r}"
            assert r["data"]["total_count"] >= 1

    asyncio.run(run())
