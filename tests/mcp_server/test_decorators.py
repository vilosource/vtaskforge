"""Tests for MCP server decorators — error handling, response serialization."""
import json
import pytest


class TestHandleErrors:
    """@handle_errors catches exceptions and returns error JSON."""

    def test_catches_exception_returns_json(self):
        from mcp_server.decorators import handle_errors

        @handle_errors
        def failing_tool():
            raise ValueError("Something broke")

        result = failing_tool()
        data = json.loads(result)
        assert data["success"] is False
        assert "Something broke" in data["message"]

    def test_passes_through_on_success(self):
        from mcp_server.decorators import handle_errors

        @handle_errors
        def good_tool():
            return json.dumps({"success": True, "data": {"id": "t1"}})

        result = good_tool()
        data = json.loads(result)
        assert data["success"] is True

    def test_catches_not_found(self):
        from mcp_server.decorators import handle_errors

        @handle_errors
        def not_found_tool():
            from tasks.models import Task
            raise Task.DoesNotExist("Task not found")

        result = not_found_tool()
        data = json.loads(result)
        assert data["success"] is False
        assert "not found" in data["message"].lower()


class TestSerializeResponse:
    """@serialize_response wraps return dict in MCP envelope + json.dumps."""

    def test_wraps_dict_in_envelope(self):
        from mcp_server.decorators import serialize_response

        @serialize_response
        def tool_returning_dict():
            return {"data": {"id": "t1", "title": "Test"}, "message": "Created task"}

        result = tool_returning_dict()
        data = json.loads(result)
        assert data["success"] is True
        assert data["data"]["id"] == "t1"
        assert data["message"] == "Created task"

    def test_includes_available_actions(self):
        from mcp_server.decorators import serialize_response

        @serialize_response
        def tool_with_actions():
            return {"data": {}, "message": "Done", "available_actions": ["vtf_task_detail"]}

        result = tool_with_actions()
        data = json.loads(result)
        assert "vtf_task_detail" in data["available_actions"]

    def test_handles_error_dict(self):
        from mcp_server.decorators import serialize_response

        @serialize_response
        def tool_returning_error():
            return {"error": True, "message": "Bad input"}

        result = tool_returning_error()
        data = json.loads(result)
        assert data["success"] is False


class TestSerializeEntity:
    """serialization.py uses v2 serializers for entity data."""

    @pytest.mark.django_db
    def test_serialize_task(self):
        from django.contrib.auth.models import User
        from projects.models import Project
        from tasks.models import Task
        from mcp_server.serialization import serialize_task

        user = User.objects.create_user("mcp-ser-user", password="pass")
        project = Project.objects.create(name="MCPSerProj", owner=user, created_by=user)
        task = Task.objects.create(title="MCPTask", project=project, created_by=user)

        data = serialize_task(task)
        assert data["id"] == task.id
        assert data["title"] == "MCPTask"
        # v2 format: project is a dict ref, not bare ID
        assert isinstance(data["project"], dict)
        assert data["project"]["name"] == "MCPSerProj"

    @pytest.mark.django_db
    def test_serialize_project(self):
        from django.contrib.auth.models import User
        from projects.models import Project
        from mcp_server.serialization import serialize_project

        user = User.objects.create_user("mcp-ser-user2", password="pass")
        project = Project.objects.create(name="MCPProj2", owner=user, created_by=user)

        data = serialize_project(project)
        assert data["id"] == project.id
        assert data["name"] == "MCPProj2"
        assert isinstance(data["owner"], dict)  # ActorRef, not string

    @pytest.mark.django_db
    def test_serialize_workplan(self):
        from django.contrib.auth.models import User
        from projects.models import Project
        from workplans.models import Workplan
        from mcp_server.serialization import serialize_workplan

        user = User.objects.create_user("mcp-ser-user3", password="pass")
        project = Project.objects.create(name="MCPProj3", owner=user, created_by=user)
        wp = Workplan.objects.create(name="MCPWP", project=project, owner=user, created_by=user)

        data = serialize_workplan(wp)
        assert data["id"] == wp.id
        assert isinstance(data["project"], dict)

    @pytest.mark.django_db
    def test_serialize_milestone(self):
        from django.contrib.auth.models import User
        from projects.models import Project
        from workplans.models import Workplan, Milestone
        from mcp_server.serialization import serialize_milestone

        user = User.objects.create_user("mcp-ser-user4", password="pass")
        project = Project.objects.create(name="MCPProj4", owner=user, created_by=user)
        wp = Workplan.objects.create(name="MCPWP2", project=project, owner=user, created_by=user)
        ms = Milestone.objects.create(name="MCPMS", workplan=wp, created_by=user)

        data = serialize_milestone(ms)
        assert data["id"] == ms.id
        assert isinstance(data["workplan"], dict)
