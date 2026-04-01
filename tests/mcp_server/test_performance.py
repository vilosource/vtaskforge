"""
Performance tests for MCP server tools.

Verifies each read-only tool completes in under 500ms with a database of
100+ tasks across multiple projects, workplans, and milestones.
"""
import json
import time

import pytest

from mcp_server.tools.board import vtf_board_overview
from mcp_server.tools.detail import vtf_task_detail
from mcp_server.tools.search import vtf_search_tasks
from mcp_server.tools._workflow_agent import vtf_next_work
from tests.factories import (
    MilestoneFactory,
    ProjectFactory,
    TaskFactory,
    WorkplanFactory,
)

PERF_THRESHOLD_SECONDS = 0.5

STATUSES = [
    "draft",
    "todo",
    "doing",
    "done",
    "blocked",
    "needs_attention",
    "pending_completion_review",
    "pending_start_review",
    "changes_requested",
    "deferred",
    "cancelled",
    "done",
]


@pytest.fixture
def seeded_db(db):
    """Seed 100+ tasks across multiple projects, milestones, workplans.

    Creates:
      - 2 projects
      - 4 workplans (2 per project)
      - 8 milestones (2 per workplan)
      - 120 tasks distributed across milestones with varied statuses,
        labels, and specs
    """
    projects = [ProjectFactory() for _ in range(2)]
    workplans = []
    for project in projects:
        for _ in range(2):
            workplans.append(WorkplanFactory(project=project))

    milestones = []
    for workplan in workplans:
        for _ in range(2):
            milestones.append(MilestoneFactory(workplan=workplan))

    tasks = []
    for i in range(120):
        milestone = milestones[i % len(milestones)]
        status = STATUSES[i % len(STATUSES)]
        labels = []
        if i % 3 == 0:
            labels = ["backend"]
        elif i % 3 == 1:
            labels = ["frontend"]
        else:
            labels = ["infra", "devops"]

        spec_text = f"implementation:\n  approach: |\n    Step-by-step for task {i}\n" if i % 2 == 0 else ""

        task = TaskFactory(
            milestone=milestone,
            workplan=milestone.workplan,
            project=milestone.workplan.project,
            status=status,
            title=f"Performance test task {i}: doing some realistic work",
            description=f"This is a realistic description for task {i} with enough content to simulate real usage.",
            labels=labels,
            spec=spec_text,
        )
        tasks.append(task)

    return {
        "projects": projects,
        "workplans": workplans,
        "milestones": milestones,
        "tasks": tasks,
        "first_task_id": tasks[0].id,
        "project_id": projects[0].id,
        "workplan_id": workplans[0].id,
    }


# ---------------------------------------------------------------------------
# Parametrized performance tests for all read-only tools
# ---------------------------------------------------------------------------


def _make_call(tool_name, kwargs):
    """Call a named tool with kwargs and return elapsed time + result."""
    tool_map = {
        "vtf_board_overview": vtf_board_overview,
        "vtf_next_work": vtf_next_work,
        "vtf_search_tasks": vtf_search_tasks,
        "vtf_task_detail": vtf_task_detail,
    }
    fn = tool_map[tool_name]
    start = time.monotonic()
    result = fn(**kwargs)
    elapsed = time.monotonic() - start
    return elapsed, result


PERF_CASES = [
    (
        "vtf_board_overview_no_filter",
        "vtf_board_overview",
        {},
    ),
    (
        "vtf_board_overview_project_filter",
        "vtf_board_overview",
        {"project_id": "PROJECT_ID"},  # replaced by fixture
    ),
    (
        "vtf_next_work_no_filter",
        "vtf_next_work",
        {},
    ),
    (
        "vtf_search_tasks_status_filter",
        "vtf_search_tasks",
        {"status": "todo"},
    ),
    (
        "vtf_search_tasks_text_query",
        "vtf_search_tasks",
        {"query": "realistic work"},
    ),
    (
        "vtf_search_tasks_labels_filter",
        "vtf_search_tasks",
        {"labels": "backend"},
    ),
    (
        "vtf_task_detail_specific_task",
        "vtf_task_detail",
        {"task_id": "FIRST_TASK_ID"},  # replaced by fixture
    ),
]


@pytest.mark.django_db
@pytest.mark.parametrize("case_name,tool_name,kwargs", PERF_CASES, ids=[c[0] for c in PERF_CASES])
def test_tool_completes_under_500ms(seeded_db, case_name, tool_name, kwargs):
    """Each read-only tool call must complete in under 500ms with 120 tasks seeded."""
    # Substitute fixture values into kwargs that use placeholder strings
    resolved_kwargs = {}
    for key, val in kwargs.items():
        if val == "PROJECT_ID":
            resolved_kwargs[key] = seeded_db["project_id"]
        elif val == "FIRST_TASK_ID":
            resolved_kwargs[key] = seeded_db["first_task_id"]
        else:
            resolved_kwargs[key] = val

    elapsed, raw_result = _make_call(tool_name, resolved_kwargs)

    # Verify it returned valid JSON
    parsed = json.loads(raw_result)
    assert "success" in parsed, f"{case_name}: response missing 'success' key"

    # Assert performance threshold
    assert elapsed < PERF_THRESHOLD_SECONDS, (
        f"{case_name} took {elapsed:.3f}s — exceeded {PERF_THRESHOLD_SECONDS}s threshold"
    )
