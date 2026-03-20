import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from vtf.cli import cli
from vtf.client import VTFAPIError


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sample-phase"


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
            "sample-phase": "ph-xyz789",
            "task-1.1": "tsk-001",
            "task-1.2": "tsk-002",
        }
    }


# --- import with valid phase dir ---

def test_import_calls_bulk_import(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    mock_client.post.assert_called_once()
    call_path = mock_client.post.call_args[0][0]
    assert call_path == "/v1/bulk/import"


def test_import_payload_contains_workplan_phase_tasks(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    # Workplan present
    assert "workplan" in payload
    assert payload["workplan"]["name"] == "Test Phase"
    # Phases list with one phase
    assert "phases" in payload
    assert len(payload["phases"]) == 1
    phase = payload["phases"][0]
    assert phase["name"] == "Test Phase"
    # Tasks present
    assert len(phase["tasks"]) == 2
    task_refs = {t["ref"] for t in phase["tasks"]}
    assert "task-1.1" in task_refs
    assert "task-1.2" in task_refs


def test_import_task_fields_mapped_correctly(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    tasks = payload["phases"][0]["tasks"]
    task_map = {t["ref"]: t for t in tasks}
    t11 = task_map["task-1.1"]
    assert t11["title"] == "Example task"
    assert "acceptance_criteria" in t11
    assert len(t11["acceptance_criteria"]) == 2


def test_import_depends_on_converted_to_links(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    links = payload.get("links", [])
    assert len(links) == 1
    link = links[0]
    assert link["source_ref"] == "task-1.2"
    assert link["target_ref"] == "task-1.1"
    assert link["type"] == "depends_on"


def test_import_prints_created_entity_ids(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    assert "wp-abc123" in result.output
    assert "tsk-001" in result.output
    assert "tsk-002" in result.output
    assert "Import successful" in result.output


# --- phase name from PHASE.md ---

def test_import_extracts_phase_name_from_heading(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload["workplan"]["name"] == "Test Phase"


def test_import_uses_dir_name_when_no_phase_md(runner, mock_client, tmp_path, successful_import_response):
    """If no PHASE.md exists, phase name falls back to directory name."""
    mock_client.post.return_value = successful_import_response
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "1.1-task.yaml").write_text(
        'id: "1.1"\nname: "Simple task"\ndepends_on: []\ndescription: ""\nacceptance_criteria: []\n'
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload["workplan"]["name"] == tmp_path.name


# --- dry-run ---

def test_dry_run_prints_payload_without_calling_api(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--dry-run"])
    assert result.exit_code == 0, result.output
    mock_client.post.assert_not_called()
    assert "Dry run" in result.output
    assert "workplan" in result.output
    assert "Would create" in result.output


def test_dry_run_shows_task_count(runner, mock_client):
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "2 tasks" in result.output
    assert "1 links" in result.output


# --- error handling ---

def test_import_api_error_prints_message_and_exits_1(runner, mock_client):
    mock_client.post.side_effect = VTFAPIError(500, {"error": {"message": "Server error"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 1
    assert "Import failed" in result.output or "Import failed" in (result.output + (result.stderr or ""))


def test_import_missing_tasks_dir_handled_gracefully(runner, mock_client, tmp_path):
    """Phase directory with no tasks/ dir produces empty tasks list."""
    (tmp_path / "PHASE.md").write_text("# Empty Phase\n")
    mock_client.post.return_value = {"ref_map": {"workplan": "wp-empty"}}
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload["phases"][0]["tasks"] == []
    assert payload["links"] == []


# --- --workplan option ---

def test_import_with_workplan_option_includes_workplan_id(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--workplan", "wp-existing"])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload.get("workplan_id") == "wp-existing"


# --- help ---

def test_import_help(runner):
    result = runner.invoke(cli, ["import", "--help"])
    assert result.exit_code == 0
    assert "phase" in result.output.lower() or "import" in result.output.lower()
    assert "--dry-run" in result.output
    assert "--workplan" in result.output
