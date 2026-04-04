"""E2E tests for the vtf CLI against live vtf-dev.

Run with: VTF_API_URL=https://vtf.dev.viloforge.com VTF_TOKEN=<token> pytest cli/tests/e2e/ -v
Requires: vtf.dev.viloforge.com accessible, valid token.
"""
import os
import pytest
from click.testing import CliRunner
from vtf.cli import cli

VTF_URL = os.environ.get("VTF_API_URL", "https://vtf.dev.viloforge.com")
VTF_TOKEN = os.environ.get("VTF_TOKEN", "88dac5ac99f96f3e10c554e0169ec2ff00260652")


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setenv("VTF_API_URL", VTF_URL)
    monkeypatch.setenv("VTF_TOKEN", VTF_TOKEN)
    return CliRunner()


class TestCLIE2E:

    def test_health(self, runner):
        result = runner.invoke(cli, ["health"])
        assert result.exit_code == 0
        assert "healthy" in result.output.lower()

    def test_project_list(self, runner):
        result = runner.invoke(cli, ["project", "list"])
        assert result.exit_code == 0
        assert "ID" in result.output
        assert "Name" in result.output

    def test_task_list(self, runner):
        result = runner.invoke(cli, ["task", "list"])
        assert result.exit_code == 0

    def test_workplan_list(self, runner):
        result = runner.invoke(cli, ["workplan", "list"])
        assert result.exit_code == 0

    def test_agent_list(self, runner):
        result = runner.invoke(cli, ["agent", "list"])
        assert result.exit_code == 0
        assert "ID" in result.output

    def test_user_list(self, runner):
        result = runner.invoke(cli, ["user", "list"])
        assert result.exit_code == 0

    def test_task_create_show_delete(self, runner):
        """Full task lifecycle: create -> show -> delete."""
        # Get a project ID
        list_result = runner.invoke(cli, ["project", "list"])
        assert list_result.exit_code == 0
        # Parse first project ID from output
        lines = list_result.output.strip().split("\n")
        proj_id = lines[2].split()[0]  # Third line (after header + separator), first column

        # Create
        create_result = runner.invoke(cli, ["task", "create", "CLI-E2E-Regression", "--project", proj_id])
        assert create_result.exit_code == 0
        assert "Created task" in create_result.output
        task_id = create_result.output.split("Created task ")[1].split(":")[0].strip()

        # Show
        show_result = runner.invoke(cli, ["task", "show", task_id])
        assert show_result.exit_code == 0
        assert "CLI-E2E-Regression" in show_result.output

        # Delete
        delete_result = runner.invoke(cli, ["task", "delete", task_id, "--yes"])
        assert delete_result.exit_code == 0
        assert "Deleted" in delete_result.output

    def test_lock_list(self, runner):
        result = runner.invoke(cli, ["lock", "list"])
        assert result.exit_code == 0

    def test_channel_mapping_list(self, runner):
        result = runner.invoke(cli, ["channel-mapping", "list"])
        assert result.exit_code == 0
