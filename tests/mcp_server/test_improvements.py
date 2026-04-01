"""TDD tests for vtf MCP server improvements.

Tests: project context middleware, smart test_command, guided guard errors,
vtf_get_context tool, vtf_plan_work tool.
"""

import json

import pytest
from tests.factories import TaskFactory, WorkplanFactory, ProjectFactory


@pytest.mark.django_db
class TestParseTestCommand:
    """test_command should accept plain strings, not just JSON."""

    def test_plain_string_wrapped_as_command(self):
        from mcp_server.utils import parse_test_command as _parse_test_command
        result = _parse_test_command("pytest tests/ -v")
        assert result == {"command": "pytest tests/ -v"}

    def test_json_string_still_works(self):
        from mcp_server.utils import parse_test_command as _parse_test_command
        result = _parse_test_command('{"unit": "pytest tests/"}')
        assert result == {"unit": "pytest tests/"}

    def test_empty_string_returns_none(self):
        from mcp_server.utils import parse_test_command as _parse_test_command
        result = _parse_test_command("")
        assert result is None

    def test_multi_key_json_preserved(self):
        from mcp_server.utils import parse_test_command as _parse_test_command
        result = _parse_test_command('{"unit": "pytest", "integration": "pytest -m integration"}')
        assert "unit" in result
        assert "integration" in result


@pytest.mark.django_db
class TestGuardViolationMessages:
    """Guard violations should include actionable next steps."""

    def test_submit_without_workplan_shows_guidance(self):
        from mcp_server.tools.manage import _action_submit
        task = TaskFactory(status="draft", workplan=None)
        result = json.loads(_action_submit(task.id))
        assert result["success"] is False
        # Must mention workplan AND the tool to use
        msg = result["message"].lower()
        assert "workplan" in msg
        assert "vtf_manage_workplan" in result["message"] or "vtf_plan_work" in result["message"]

    def test_submit_with_workplan_succeeds(self):
        from mcp_server.tools.manage import _action_submit
        workplan = WorkplanFactory(status="active")
        task = TaskFactory(status="draft", workplan=workplan)
        result = json.loads(_action_submit(task.id))
        assert result["success"] is True


@pytest.mark.django_db
class TestProjectContext:
    """Project context middleware stores X-VTF-Project for tools."""

    def test_context_var_set_from_header(self):
        from mcp_server.project_context import _current_project, get_default_project
        _current_project.set("test-project-123")
        assert get_default_project() == "test-project-123"
        _current_project.set(None)

    def test_context_var_default_is_none(self):
        from mcp_server.project_context import get_default_project
        assert get_default_project() is None


@pytest.mark.django_db
class TestVtfGetContext:
    """vtf_get_context returns project-scoped overview."""

    def test_returns_project_overview(self):
        from mcp_server.tools.context import vtf_get_context
        from mcp_server.project_context import _current_project

        project = ProjectFactory()
        workplan = WorkplanFactory(project=project, status="active")
        TaskFactory(project=project, workplan=workplan, status="done")
        TaskFactory(project=project, workplan=workplan, status="todo")
        TaskFactory(project=project, workplan=workplan, status="needs_attention")

        _current_project.set(project.id)
        result = json.loads(vtf_get_context())
        _current_project.set(None)

        assert result["success"] is True
        data = result["data"]
        assert "workplans" in data
        assert "counts" in data
        assert "attention_items" in data

    def test_uses_explicit_project_id(self):
        from mcp_server.tools.context import vtf_get_context

        project = ProjectFactory()
        TaskFactory(project=project, status="done")

        result = json.loads(vtf_get_context(project_id=project.id))
        assert result["success"] is True

    def test_errors_without_project(self):
        from mcp_server.tools.context import vtf_get_context
        from mcp_server.project_context import _current_project
        _current_project.set(None)
        result = json.loads(vtf_get_context())
        assert result["success"] is False
        assert "project" in result["message"].lower()


@pytest.mark.django_db
class TestVtfPlanWork:
    """vtf_plan_work creates workplan + tasks in one call."""

    def test_creates_workplan_and_tasks(self):
        from mcp_server.tools.planning import vtf_plan_work

        project = ProjectFactory()
        tasks_json = json.dumps([
            {"title": "Add auth endpoint", "spec": "Implement OAuth2", "test_command": "pytest tests/test_auth.py"},
            {"title": "Add rate limiting", "spec": "Add middleware", "test_command": "pytest tests/test_rate.py"},
        ])

        result = json.loads(vtf_plan_work(
            workplan_name="Auth Sprint",
            tasks=tasks_json,
            project_id=project.id,
        ))

        assert result["success"] is True
        data = result["data"]
        assert "workplan_id" in data
        assert len(data["tasks"]) == 2
        assert all(t["status"] == "todo" for t in data["tasks"])

    def test_plain_string_test_command_accepted(self):
        from mcp_server.tools.planning import vtf_plan_work

        project = ProjectFactory()
        tasks_json = json.dumps([
            {"title": "Simple task", "spec": "Do the thing", "test_command": "echo ok"},
        ])

        result = json.loads(vtf_plan_work(
            workplan_name="Test Plan",
            tasks=tasks_json,
            project_id=project.id,
        ))

        assert result["success"] is True

    def test_uses_default_project_from_context(self):
        from mcp_server.tools.planning import vtf_plan_work
        from mcp_server.project_context import _current_project

        project = ProjectFactory()
        _current_project.set(project.id)

        result = json.loads(vtf_plan_work(
            workplan_name="Context Plan",
            tasks=json.dumps([{"title": "T1", "spec": "S1"}]),
        ))
        _current_project.set(None)

        assert result["success"] is True

    def test_errors_without_project(self):
        from mcp_server.tools.planning import vtf_plan_work
        from mcp_server.project_context import _current_project
        _current_project.set(None)

        result = json.loads(vtf_plan_work(
            workplan_name="No Project",
            tasks=json.dumps([{"title": "T1", "spec": "S1"}]),
        ))

        assert result["success"] is False
        assert "project" in result["message"].lower()

    def test_errors_on_invalid_tasks_json(self):
        from mcp_server.tools.planning import vtf_plan_work

        project = ProjectFactory()
        result = json.loads(vtf_plan_work(
            workplan_name="Bad JSON",
            tasks="not json at all",
            project_id=project.id,
        ))

        assert result["success"] is False
