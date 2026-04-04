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
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    mock_client.post.assert_called_once()
    call_path = mock_client.post.call_args[0][0]
    assert call_path == "/v1/bulk/import"


def test_import_payload_contains_workplan_milestone_tasks(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    # Workplan present
    assert "workplan" in payload
    assert payload["workplan"]["name"] == "Test Milestone"
    # Milestones list with one milestone
    assert "milestones" in payload
    assert len(payload["milestones"]) == 1
    milestone = payload["milestones"][0]
    assert milestone["name"] == "Test Milestone"
    # Tasks present
    assert len(milestone["tasks"]) == 2
    task_refs = {t["ref"] for t in milestone["tasks"]}
    assert "task-1.1" in task_refs
    assert "task-1.2" in task_refs


def test_import_task_fields_mapped_correctly(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    tasks = payload["milestones"][0]["tasks"]
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


# --- milestone name from MILESTONE.md ---

def test_import_extracts_milestone_name_from_heading(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload["workplan"]["name"] == "Test Milestone"


def test_import_uses_dir_name_when_no_milestone_md(runner, mock_client, tmp_path, successful_import_response):
    """If no MILESTONE.md exists, milestone name falls back to directory name."""
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
    mock_client.post.side_effect = VtfError("UNKNOWN", 500, {"error": {"message": "Server error"}})
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 1
    assert "Import failed" in result.output or "Import failed" in (result.output + (result.stderr or ""))


def test_import_missing_tasks_dir_exits_with_error(runner, mock_client, tmp_path):
    """Milestone directory with no tasks/ dir should fail with helpful error."""
    (tmp_path / "MILESTONE.md").write_text("# Empty Milestone\n")
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(tmp_path)])
    assert result.exit_code == 1
    mock_client.post.assert_not_called()


def test_import_empty_tasks_dir_exits_with_error(runner, mock_client, tmp_path):
    """Milestone directory with empty tasks/ dir should fail with helpful error."""
    (tmp_path / "MILESTONE.md").write_text("# Empty Milestone\n")
    (tmp_path / "tasks").mkdir()
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(tmp_path)])
    assert result.exit_code == 1
    mock_client.post.assert_not_called()


# --- --workplan option ---

def test_import_with_workplan_option_includes_workplan_id(runner, mock_client, successful_import_response):
    mock_client.get.return_value = {"project": "prj-inferred", "id": "wp-existing", "name": "WP"}
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--workplan", "wp-existing"])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload.get("workplan_id") == "wp-existing"


def test_import_with_project_option_includes_project_id(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--project", "prj-existing"])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload.get("project_id") == "prj-existing"


def test_import_without_project_option_creates_project(runner, mock_client, successful_import_response):
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert "project" in payload
    assert payload["project"]["name"] == "Test Milestone"


# --- help ---

def test_import_help(runner):
    result = runner.invoke(cli, ["import", "--help"])
    assert result.exit_code == 0
    assert "milestone" in result.output.lower() or "import" in result.output.lower()
    assert "--dry-run" in result.output
    assert "--workplan" in result.output


# --- inline depends_on fallback ---

def test_import_inline_depends_on_when_no_dag(runner, mock_client, tmp_path, successful_import_response):
    """When dag.yaml is absent, depends_on from task specs should produce links."""
    mock_client.post.return_value = successful_import_response
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "1.1-first.yaml").write_text(
        'id: "1.1"\nname: "First task"\ndepends_on: []\ndescription: ""\nacceptance_criteria: []\n'
    )
    (tasks_dir / "1.2-second.yaml").write_text(
        'id: "1.2"\nname: "Second task"\ndepends_on: ["1.1"]\ndescription: ""\nacceptance_criteria: []\n'
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    links = payload.get("links", [])
    assert len(links) == 1
    assert links[0]["source_ref"] == "task-1.2"
    assert links[0]["target_ref"] == "task-1.1"
    assert links[0]["type"] == "depends_on"


def test_import_dag_yaml_takes_precedence_over_inline(runner, mock_client, successful_import_response):
    """When dag.yaml exists, inline depends_on should be ignored."""
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    links = payload.get("links", [])
    # dag.yaml has 1.2 depends on 1.1 — should use that, not inline
    assert len(links) == 1
    assert links[0]["source_ref"] == "task-1.2"
    assert links[0]["target_ref"] == "task-1.1"


def test_import_inline_depends_on_string_handled(runner, mock_client, tmp_path, successful_import_response):
    """Inline depends_on as a single string (not list) should still work."""
    mock_client.post.return_value = successful_import_response
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "1.1-first.yaml").write_text(
        'id: "1.1"\nname: "First task"\ndescription: ""\nacceptance_criteria: []\n'
    )
    (tasks_dir / "1.2-second.yaml").write_text(
        'id: "1.2"\nname: "Second task"\ndepends_on: "1.1"\ndescription: ""\nacceptance_criteria: []\n'
    )
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    links = payload.get("links", [])
    assert len(links) == 1
    assert links[0]["source_ref"] == "task-1.2"
    assert links[0]["target_ref"] == "task-1.1"


def test_import_with_workplan_infers_project_from_api(runner, mock_client, successful_import_response):
    """When --workplan is given but --project is not, project should be inferred from workplan."""
    mock_client.get.return_value = {"project": "prj-from-workplan", "id": "wp-existing", "name": "WP"}
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--workplan", "wp-existing"])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload.get("project_id") == "prj-from-workplan"
    assert "project" not in payload  # should NOT create a new project


def test_import_with_workplan_and_project_uses_explicit_project(runner, mock_client, successful_import_response):
    """When both --workplan and --project are given, use the explicit project."""
    mock_client.post.return_value = successful_import_response
    with patch("vtf.cli.get_client", return_value=mock_client):
        result = runner.invoke(cli, ["import", str(FIXTURES_DIR), "--workplan", "wp-existing", "--project", "prj-explicit"])
    assert result.exit_code == 0, result.output
    payload = mock_client.post.call_args[0][1]
    assert payload.get("project_id") == "prj-explicit"
    mock_client.get.assert_not_called()  # should NOT look up workplan
