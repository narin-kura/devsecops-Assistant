"""A small JSON-backed catalog of what specialists know about each app.

Every specialist reads and writes here alongside its domain-specific work,
keyed by app id, so a later specialist (security, infra, secrets, ...) can
look up what an earlier one already found instead of starting blind. Scoped
per project: the registry lives inside the project it describes, the same
way `.git` does.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY_DIRNAME = ".devsecops"
REGISTRY_FILENAME = "registry.json"


def _registry_path(project_path: str) -> Path:
    return Path(project_path).resolve() / REGISTRY_DIRNAME / REGISTRY_FILENAME


def _load(project_path: str) -> Dict[str, Any]:
    path = _registry_path(project_path)
    if not path.exists():
        return {"apps": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(project_path: str, data: Dict[str, Any]) -> None:
    path = _registry_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def app_id_for(project_path: str) -> str:
    """Default app id derived from the project directory name."""
    return Path(project_path).resolve().name


def register_app(project_path: str, app_id: str, **fields: Any) -> Dict[str, Any]:
    """Create or update an app's entry with plain scalar fields (language, framework, ...)."""
    data = _load(project_path)
    entry = data["apps"].setdefault(app_id, {})
    entry.update(fields)
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(project_path, data)
    return entry


def link(project_path: str, app_id: str, domain: str, value: Dict[str, Any]) -> Dict[str, Any]:
    """Attach a domain-specific finding to an app, e.g. link(path, "myapp", "ci_cd", {...}).

    Each domain accumulates a list of entries (an app can be onboarded to more
    than one CI tool, scanned more than once, etc.) rather than overwriting.
    """
    data = _load(project_path)
    entry = data["apps"].setdefault(app_id, {})
    entry.setdefault(domain, [])
    entry[domain].append({**value, "recorded_at": datetime.now(timezone.utc).isoformat()})
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(project_path, data)
    return entry


def get_app(project_path: str, app_id: str) -> Optional[Dict[str, Any]]:
    return _load(project_path)["apps"].get(app_id)


def list_apps(project_path: str) -> List[str]:
    return sorted(_load(project_path)["apps"].keys())
