import os
import yaml
from pathlib import Path

CONFIG_DIR = Path.home() / ".vtf"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


class Config:
    def __init__(self, config_file=None):
        self._config_file = Path(config_file) if config_file else CONFIG_FILE
        self._config_dir = self._config_file.parent
        self._data = {}
        self._load()

    def _load(self):
        if self._config_file.exists():
            with open(self._config_file) as f:
                self._data = yaml.safe_load(f) or {}

    def get(self, key, default=None):
        # Env vars take precedence
        env_key = f"VTF_{key.upper()}"
        env_val = os.environ.get(env_key)
        if env_val:
            return env_val
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w") as f:
            yaml.dump(self._data, f)

    def load(self):
        self._load()

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w") as f:
            yaml.dump(self._data, f)

    def get_api_url(self):
        return self.get("api_url", "http://localhost:8000")

    def get_token(self):
        return self.get("token")

    @property
    def api_url(self):
        return self.get_api_url()

    @property
    def token(self):
        return self.get_token()

    def get_project(self):
        return self.get("project")

    @property
    def project(self):
        return self.get_project()
