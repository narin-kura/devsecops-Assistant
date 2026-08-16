import os
from typing import Any, Dict

import yaml


class ConfigError(RuntimeError):
    """Raised when configuration problems are detected."""


def load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def getenv_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"Environment variable {name!r} is required but not set.")
    return value
