import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf_sdk.exceptions import VtfError


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample-milestone"


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def successful_import_response():
    return {
        "ref_map": {
            "workplan": "wp-abc123",
            "sample-milestone": "ms-xyz789",
            "task-1.1": "tsk-001",
            "task-1.2": "tsk-002",
        }
    }


# --- import with valid milestone dir ---

def test_import_calls_bulk_import(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    mock_client.bulk.do_import.assert_called_once()


def test_import_payload_contains_workplan_milestone_tasks(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    call_kwargs = mock_client.bulk.do_import.call_args[1]
    payload = call_kwargs["payload"]
    assert "workplan" in payload
    assert payload["workplan"]["name"] == "Test Milestone"
    assert "milestones" in payload
    assert len(payload["milestones"]) == 1
    assert len(payload["milestones"][0]["tasks"]) == 2


def test_import_task_fields_mapped_correctly(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    tasks = payload["milestones"][0]["tasks"]
    task_map = {t["ref"]: t for t in tasks}
    t11 = task_map["task-1.1"]
    assert t11["title"] == "Example task"
    assert "acceptance_criteria" in t11
    assert len(t11["acceptance_criteria"]) == 2


def test_import_routes_legacy_requires_to_required_tags(runner, mock_client, successful_import_response):
    """Legacy YAML `requires:` (capability tag strings) must land in payload
    `required_tags` after migration 0014. Backward-compat for task YAML
    written before the field was renamed.
    """
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    tasks = payload["milestones"][0]["tasks"]
    task_map = {t["ref"]: t for t in tasks}
    # 1.1 has `requires: [executor, pi]` in its YAML; 1.2 has none.
    assert task_map["task-1.1"]["required_tags"] == ["executor", "pi"]
    assert task_map["task-1.2"]["required_tags"] == []
    # `requires` in the task entry is reserved for task dep refs (built
    # from depends_on/dag.yaml via the links list); not present on entries.
    assert "requires" not in task_map["task-1.1"]


def test_import_prefers_explicit_required_tags_over_legacy_requires(runner, mock_client, successful_import_response, tmp_path):
    """When YAML has both `required_tags` and legacy `requires`, both merge
    into payload required_tags (required_tags first, no duplicates).
    """
    # Build a one-off fixture
    ms = tmp_path / "ms"
    (ms / "tasks").mkdir(parents=True)
    (ms / "MILESTONE.md").write_text("# Test\n")
    (ms / "tasks" / "1.yaml").write_text(
        "id: '1'\nname: 'T'\ndepends_on: []\n"
        "required_tags: [executor, gpu]\n"
        "requires: [executor, pi]\n"
    )
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(ms)])
    assert result.exit_code == 0, result.output
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    tasks = payload["milestones"][0]["tasks"]
    assert tasks[0]["required_tags"] == ["executor", "gpu", "pi"]


def test_import_prints_ref_map(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0
    assert "Import successful" in result.output
    assert "wp-abc123" in result.output


def test_import_dry_run(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--dry-run"])
    assert result.exit_code == 0
    assert "Dry run" in result.output
    mock_client.bulk.do_import.assert_not_called()


def test_import_with_workplan_option_includes_workplan_id(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    # Mock workplans.get to return a workplan with project
    from vtf_sdk.entities import Workplan
    from vtf_sdk.refs import ProjectRef
    mock_client.workplans.get.return_value = Workplan.model_validate({
        "id": "wp-existing", "name": "Existing WP", "status": "active",
        "project": ProjectRef(id="proj-from-wp", name="Proj"),
    })
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--workplan", "wp-existing"])
    assert result.exit_code == 0, result.output
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    assert payload.get("workplan_id") == "wp-existing"
    assert payload.get("project_id") == "proj-from-wp"


def test_import_with_project_option_includes_project_id(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--project", "proj-explicit"])
    assert result.exit_code == 0, result.output
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    assert payload.get("project_id") == "proj-explicit"


def test_import_without_project_option_creates_project(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    assert "project" in payload  # creates new project


def test_import_api_error_prints_message_and_exits_1(runner, mock_client):
    mock_client.bulk.do_import.side_effect = VtfError("VALIDATION_ERROR", "Import failed")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 1
    assert "Import failed" in result.output


def test_import_nonexistent_dir(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", "/nonexistent/path"])
    assert result.exit_code != 0


# --- dag.yaml handling ---

def test_import_inline_depends_on_when_no_dag(runner, mock_client, successful_import_response, tmp_path):
    """When no dag.yaml exists, use inline depends_on from task specs."""
    # Create a minimal milestone dir without dag.yaml
    ms_dir = tmp_path / "test-ms"
    ms_dir.mkdir()
    (ms_dir / "MILESTONE.md").write_text("# Inline Deps Test\nDescription here.\n")
    tasks_dir = ms_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "1.1.yaml").write_text(
        "id: 1.1\nname: Task One\ndescription: First\ndepends_on:\n  - 1.2\n"
    )
    (tasks_dir / "1.2.yaml").write_text(
        "id: 1.2\nname: Task Two\ndescription: Second\n"
    )
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(ms_dir)])
    assert result.exit_code == 0, result.output
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    links = payload.get("links", [])
    assert len(links) >= 1


def test_import_dag_yaml_takes_precedence_over_inline(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    links = payload.get("links", [])
    # dag.yaml in fixtures should produce links
    assert isinstance(links, list)


def test_import_with_workplan_and_project_uses_explicit_project(runner, mock_client, successful_import_response):
    mock_client.bulk.do_import.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--workplan", "wp-1", "--project", "proj-explicit"])
    assert result.exit_code == 0
    payload = mock_client.bulk.do_import.call_args[1]["payload"]
    assert payload.get("project_id") == "proj-explicit"
    assert payload.get("workplan_id") == "wp-1"


# --- help ---

def test_import_help(runner):
    result = runner.invoke(cli, ["import", "--help"])
    assert result.exit_code == 0
    assert "--workplan" in result.output
    assert "--project" in result.output
    assert "--dry-run" in result.output
