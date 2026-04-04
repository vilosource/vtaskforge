"""Helper utilities for mocking the SDK client in CLI tests."""
from unittest.mock import MagicMock
from vtf_sdk.entities import Task, Project, Workplan, Milestone, Agent, Review, Note, TaskEvent
from vtf_sdk.pagination import PagedResult
from vtf_sdk.refs import ProjectRef, WorkplanRef, MilestoneRef, TaskRef, UserActor
from vtf_sdk.exceptions import VtfError


def make_task(**overrides):
    """Build a Task entity with defaults for CLI test assertions."""
    defaults = {
        "id": "task-001", "title": "Test Task", "description": "",
        "status": "draft", "project": ProjectRef(id="p1", name="TestProj"),
        "labels": [], "acceptance_criteria": [], "requires": [],
        "spec": "", "agent_model": "", "test_command": {}, "judge": False,
        "isolation": "", "retry_count": 0,
    }
    defaults.update(overrides)
    return Task.model_validate(defaults)


def make_project(**overrides):
    defaults = {
        "id": "proj-001", "name": "Test Project", "description": "",
        "status": "active", "repo_url": "", "default_branch": "main", "tags": [],
    }
    defaults.update(overrides)
    return Project.model_validate(defaults)


def make_paged(items, has_more=False):
    """Build a PagedResult from a list of items."""
    return PagedResult(items=items, has_more=has_more)


def make_vtf_error(message="API Error", code="UNKNOWN"):
    return VtfError(code, message)
