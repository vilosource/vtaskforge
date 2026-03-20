import pytest
from pathlib import Path
from vtf.config import Config
from vtf.client import VTFClient


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Fixture providing an isolated config directory."""
    cfg_dir = tmp_path / ".vtf"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.yaml"
    # Patch environment variables that would interfere
    monkeypatch.delenv("VTF_API_URL", raising=False)
    monkeypatch.delenv("VTF_TOKEN", raising=False)
    return cfg_file


@pytest.fixture
def mock_config(config_dir):
    """Fixture providing a Config instance backed by a temp directory."""
    return Config(config_file=config_dir)


@pytest.fixture
def mock_api(requests_mock):
    """Fixture providing a requests_mock instance."""
    return requests_mock
