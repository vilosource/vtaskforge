import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError
from vtf_sdk.entities import Workplan, Milestone
from vtf_sdk.refs import ProjectRef, WorkplanRef
from tests.sdk_mock_helpers import make_paged


def make_wp(**overrides):
    defaults = {"id": "wp-001", "name": "Test WP", "status": "active", "description": "", "tags": []}
    defaults.update(overrides)
    return Workplan.model_validate(defaults)


def make_ms(**overrides):
    defaults = {"id": "ms-001", "name": "Sprint 1", "status": "active", "order": 1, "description": "",
                "workplan": WorkplanRef(id="wp-001", name="WP")}
    defaults.update(overrides)
    return Milestone.model_validate(defaults)


@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_client():
    return MagicMock()


# --- workplan create ---

def test_workplan_create_success(runner, mock_client):
    mock_client.workplans.create.return_value = make_wp(id="wp-123", name="Test Workplan")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create", "--name", "Test Workplan", "--project", "proj-123"])
    assert result.exit_code == 0
    assert "Created workplan wp-123" in result.output

def test_workplan_create_with_tags(runner, mock_client):
    mock_client.workplans.create.return_value = make_wp(id="wp-456", name="Tagged Plan")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create", "--name", "Tagged Plan", "--tags", "a,b", "--project", "p1"])
    assert result.exit_code == 0
    call_kwargs = mock_client.workplans.create.call_args[1]
    assert call_kwargs["tags"] == ["a", "b"]

def test_workplan_create_api_error(runner, mock_client):
    mock_client.workplans.create.side_effect = VtfError("VALIDATION_ERROR", "Bad request")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create", "--name", "Fail", "--project", "p1"])
    assert result.exit_code == 1

def test_workplan_create_missing_name(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "create"])
    assert result.exit_code != 0

def test_workplan_create_missing_project(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client), \
         patch("vtf.commands.workplan.Config") as MockCfg:
        MockCfg.return_value.project = None
        result = runner.invoke(cli, ["workplan", "create", "--name", "No Project"])
    assert result.exit_code == 1
    assert "project is required" in result.output

def test_workplan_create_with_default_project(runner, mock_client):
    mock_client.workplans.create.return_value = make_wp(id="wp-def", name="Default Plan")
    with patch("vtf.cli.get_client", return_value=mock_client), \
         patch("vtf.commands.workplan.Config") as MockCfg:
        MockCfg.return_value.project = "proj-default"
        result = runner.invoke(cli, ["workplan", "create", "--name", "Default Plan"])
    assert result.exit_code == 0

# --- workplan list ---

def test_workplan_list_success(runner, mock_client):
    mock_client.workplans.list.return_value = make_paged([
        make_wp(id="wp-001", name="Plan Alpha", status="active"),
        make_wp(id="wp-002", name="Plan Beta", status="completed"),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list"])
    assert result.exit_code == 0
    assert "wp-001" in result.output
    assert "Plan Alpha" in result.output

def test_workplan_list_empty(runner, mock_client):
    mock_client.workplans.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list"])
    assert result.exit_code == 0
    assert "No workplans found" in result.output

def test_workplan_list_api_error(runner, mock_client):
    mock_client.workplans.list.side_effect = VtfError("UNKNOWN", "Server error")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list"])
    assert result.exit_code == 1

def test_workplan_list_with_project_filter(runner, mock_client):
    mock_client.workplans.list.return_value = make_paged([make_wp()])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "list", "--project", "proj-123"])
    assert result.exit_code == 0

# --- workplan show ---

def test_workplan_show_success(runner, mock_client):
    mock_client.workplans.get.return_value = make_wp(
        id="wp-abc", name="Detail Plan", description="A detailed plan", tags=["infra", "cloud"])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "show", "wp-abc"])
    assert result.exit_code == 0
    assert "wp-abc" in result.output
    assert "Detail Plan" in result.output
    assert "infra" in result.output

def test_workplan_show_not_found(runner, mock_client):
    mock_client.workplans.get.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "show", "nonexistent"])
    assert result.exit_code == 1

def test_workplan_show_no_tags(runner, mock_client):
    mock_client.workplans.get.return_value = make_wp(id="wp-notags", name="No Tags Plan")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "show", "wp-notags"])
    assert result.exit_code == 0
    assert "Tags:" in result.output

# --- workplan archive/complete ---

def test_workplan_archive_success(runner, mock_client):
    mock_client.workplans.archive.return_value = make_wp(status="archived")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "archive", "wp-abc"])
    assert result.exit_code == 0
    assert "Archived workplan wp-abc" in result.output

def test_workplan_archive_not_found(runner, mock_client):
    mock_client.workplans.archive.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "archive", "missing-id"])
    assert result.exit_code == 1

def test_workplan_complete_success(runner, mock_client):
    mock_client.workplans.complete.return_value = make_wp(status="completed")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "complete", "wp-abc"])
    assert result.exit_code == 0
    assert "Completed workplan wp-abc" in result.output

def test_workplan_complete_api_error(runner, mock_client):
    mock_client.workplans.complete.side_effect = VtfError("UNKNOWN", "Already completed")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "complete", "wp-done"])
    assert result.exit_code == 1

# --- workplan stats ---

def test_workplan_stats_success(runner, mock_client):
    mock_client.workplans.stats.return_value = {"total_tasks": 10, "completed_percentage": 50, "by_status": {"todo": 3, "doing": 2, "done": 5}}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "stats", "wp-abc"])
    assert result.exit_code == 0
    assert "Total tasks: 10" in result.output
    assert "50%" in result.output

def test_workplan_stats_no_by_status(runner, mock_client):
    mock_client.workplans.stats.return_value = {"total_tasks": 0, "completed_percentage": 0}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "stats", "wp-empty"])
    assert result.exit_code == 0
    assert "Total tasks: 0" in result.output

def test_workplan_stats_api_error(runner, mock_client):
    mock_client.workplans.stats.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["workplan", "stats", "nonexistent"])
    assert result.exit_code == 1

# --- milestone create ---

def test_milestone_create_success(runner, mock_client):
    mock_client.milestones.create.return_value = make_ms(id="ms-001", name="Sprint 1")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--name", "Sprint 1", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    assert "ms-001" in result.output

def test_milestone_create_with_description_and_order(runner, mock_client):
    mock_client.milestones.create.return_value = make_ms(id="ms-002", name="Sprint 2")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--name", "Sprint 2", "--workplan", "wp-abc", "--description", "Second sprint", "--sort-order", "2"])
    assert result.exit_code == 0
    call_kwargs = mock_client.milestones.create.call_args[1]
    assert call_kwargs["description"] == "Second sprint"
    assert call_kwargs["order"] == 2

def test_milestone_create_missing_name(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--workplan", "wp-abc"])
    assert result.exit_code != 0

def test_milestone_create_missing_workplan(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--name", "Sprint 1"])
    assert result.exit_code != 0

def test_milestone_create_api_error(runner, mock_client):
    mock_client.milestones.create.side_effect = VtfError("VALIDATION_ERROR", "Bad request")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "create", "--name", "Fail", "--workplan", "wp-abc"])
    assert result.exit_code == 1

# --- milestone list ---

def test_milestone_list_success(runner, mock_client):
    mock_client.milestones.list.return_value = make_paged([
        make_ms(id="ms-001", name="Sprint 1", order=1),
        make_ms(id="ms-002", name="Sprint 2", order=2),
    ])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    assert "ms-001" in result.output
    assert "Sprint 1" in result.output

def test_milestone_list_empty(runner, mock_client):
    mock_client.milestones.list.return_value = make_paged([])
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list", "--workplan", "wp-abc"])
    assert result.exit_code == 0
    assert "No milestones found" in result.output

def test_milestone_list_missing_workplan(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list"])
    assert result.exit_code != 0

def test_milestone_list_api_error(runner, mock_client):
    mock_client.milestones.list.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "list", "--workplan", "wp-missing"])
    assert result.exit_code == 1

# --- milestone show ---

def test_milestone_show_success(runner, mock_client):
    mock_client.milestones.get.return_value = make_ms(id="ms-001", name="Sprint 1", description="First sprint")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "show", "ms-001"])
    assert result.exit_code == 0
    assert "ms-001" in result.output
    assert "Sprint 1" in result.output

def test_milestone_show_not_found(runner, mock_client):
    mock_client.milestones.get.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "show", "nonexistent"])
    assert result.exit_code == 1

# --- milestone update ---

def test_milestone_update_name(runner, mock_client):
    mock_client.milestones.update.return_value = make_ms(name="Updated Sprint")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001", "--name", "Updated Sprint"])
    assert result.exit_code == 0
    assert "Updated milestone ms-001" in result.output

def test_milestone_update_description(runner, mock_client):
    mock_client.milestones.update.return_value = make_ms(description="New desc")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001", "--description", "New desc"])
    assert result.exit_code == 0

def test_milestone_update_order(runner, mock_client):
    mock_client.milestones.update.return_value = make_ms(order=5)
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001", "--sort-order", "5"])
    assert result.exit_code == 0

def test_milestone_update_no_fields(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "ms-001"])
    assert result.exit_code == 1

def test_milestone_update_api_error(runner, mock_client):
    mock_client.milestones.update.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "update", "missing", "--name", "Fail"])
    assert result.exit_code == 1

# --- milestone stats ---

def test_milestone_stats_success(runner, mock_client):
    mock_client.milestones.stats.return_value = {"total_tasks": 6, "completed_percentage": 33, "by_status": {"todo": 2, "doing": 2, "done": 2}}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "stats", "ms-abc"])
    assert result.exit_code == 0
    assert "Total tasks: 6" in result.output

def test_milestone_stats_no_by_status(runner, mock_client):
    mock_client.milestones.stats.return_value = {"total_tasks": 0, "completed_percentage": 0}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "stats", "ms-empty"])
    assert result.exit_code == 0

def test_milestone_stats_api_error(runner, mock_client):
    mock_client.milestones.stats.side_effect = VtfError("NOT_FOUND", "Not found")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["milestone", "stats", "nonexistent"])
    assert result.exit_code == 1

# --- help ---

def test_workplan_help(runner):
    result = runner.invoke(cli, ["workplan", "--help"])
    assert result.exit_code == 0

def test_workplan_create_help(runner):
    result = runner.invoke(cli, ["workplan", "create", "--help"])
    assert result.exit_code == 0

def test_milestone_help(runner):
    result = runner.invoke(cli, ["milestone", "--help"])
    assert result.exit_code == 0
