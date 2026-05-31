"""CLI tests for `vtf project var probe` (C.3 Slice 5 #5)."""
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vtf.cli import cli

ENV = {"VTF_PROBE_URL": "https://vafi-probe.dev.viloforge.com", "VTF_TOKEN": "tok"}


@pytest.fixture
def runner():
    return CliRunner()


def _resp(status_code, payload):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = payload
    return r


def test_probe_pass(runner):
    report = {
        "project": "p1", "slug": "abad", "environment": "dev", "result": "PASS",
        "variables": [
            {"name": "GH_TOKEN", "role": "executor", "result": "success", "size_bytes": 47, "required": True},
            {"name": "SENTRY_DSN", "role": "executor", "result": "not_found", "size_bytes": None, "required": False},
        ],
    }
    with patch("httpx.post", return_value=_resp(200, report)) as post:
        r = runner.invoke(cli, ["project", "var", "probe", "p1"], env=ENV)
    assert r.exit_code == 0
    assert "✓ GH_TOKEN" in r.output and "47 bytes" in r.output
    assert "[optional]" in r.output  # SENTRY_DSN optional
    assert "Result: PASS" in r.output
    # posts to the probe endpoint with the caller token + project param
    _, kwargs = post.call_args
    assert kwargs["params"] == {"project": "p1"}
    assert kwargs["headers"]["Authorization"] == "Token tok"


def test_probe_fail_exits_nonzero(runner):
    report = {
        "project": "p1", "slug": "abad", "environment": "dev", "result": "FAIL",
        "variables": [{"name": "GH_TOKEN", "role": "executor", "result": "not_found",
                       "size_bytes": None, "required": True}],
    }
    with patch("httpx.post", return_value=_resp(200, report)):
        r = runner.invoke(cli, ["project", "var", "probe", "p1"], env=ENV)
    assert r.exit_code == 1
    assert "✗ GH_TOKEN" in r.output and "Result: FAIL" in r.output


def test_probe_no_url_configured(runner):
    with patch("httpx.post") as post:
        r = runner.invoke(cli, ["project", "var", "probe", "p1"], env={"VTF_TOKEN": "tok"})
    assert r.exit_code == 2
    assert "probe URL not set" in r.output
    post.assert_not_called()


def test_probe_endpoint_error_exits_1(runner):
    with patch("httpx.post", return_value=_resp(403, {"error": "not authorized for this project"})):
        r = runner.invoke(cli, ["project", "var", "probe", "p1"], env=ENV)
    assert r.exit_code == 1
    assert "not authorized" in r.output
