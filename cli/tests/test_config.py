import pytest
import yaml
from pathlib import Path
from vtf.config import Config


def test_default_api_url(mock_config):
    assert mock_config.api_url == "http://localhost:8000"


def test_default_token_is_none(mock_config):
    assert mock_config.token is None


def test_set_and_get_api_url(mock_config):
    mock_config.set("api_url", "http://example.com")
    assert mock_config.api_url == "http://example.com"


def test_set_and_get_token(mock_config):
    mock_config.set("token", "mytoken123")
    assert mock_config.token == "mytoken123"


def test_set_writes_to_file(config_dir, mock_config):
    mock_config.set("api_url", "http://example.com")
    assert config_dir.exists()
    with open(config_dir) as f:
        data = yaml.safe_load(f)
    assert data["api_url"] == "http://example.com"


def test_load_reads_existing_file(config_dir):
    config_dir.write_text(yaml.dump({"api_url": "http://loaded.com", "token": "tok123"}))
    cfg = Config(config_file=config_dir)
    assert cfg.api_url == "http://loaded.com"
    assert cfg.token == "tok123"


def test_env_var_overrides_api_url(monkeypatch, mock_config):
    mock_config.set("api_url", "http://from-file.com")
    monkeypatch.setenv("VTF_API_URL", "http://from-env.com")
    assert mock_config.api_url == "http://from-env.com"


def test_env_var_overrides_token(monkeypatch, mock_config):
    mock_config.set("token", "file-token")
    monkeypatch.setenv("VTF_TOKEN", "env-token")
    assert mock_config.token == "env-token"


def test_env_var_api_url_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setenv("VTF_API_URL", "http://env-only.com")
    cfg = Config(config_file=tmp_path / "nonexistent.yaml")
    assert cfg.api_url == "http://env-only.com"


def test_config_dir_created_on_set(tmp_path, monkeypatch):
    monkeypatch.delenv("VTF_API_URL", raising=False)
    monkeypatch.delenv("VTF_TOKEN", raising=False)
    nested_dir = tmp_path / "a" / "b" / ".vtf"
    cfg_file = nested_dir / "config.yaml"
    cfg = Config(config_file=cfg_file)
    cfg.set("api_url", "http://test.com")
    assert cfg_file.exists()


def test_get_with_default(mock_config):
    assert mock_config.get("nonexistent_key", "fallback") == "fallback"


def test_get_api_url_method(mock_config):
    assert mock_config.get_api_url() == "http://localhost:8000"


def test_get_token_method(mock_config):
    assert mock_config.get_token() is None
