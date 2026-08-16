"""Dependency-ecosystem mapping for Dependabot config generation.

Dependabot identifies what to scan via a fixed set of "package-ecosystem"
values (https://docs.github.com/code-security/dependabot) — this maps a
detected (language, package_manager) pair onto the right one.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..ci_onboard.detector import ProjectProfile

_ECOSYSTEM_BY_LANG_AND_MANAGER: Dict[str, Dict[str, str]] = {
    "python": {"pip": "pip", "poetry": "pip", "pipenv": "pip"},
    "javascript": {"npm": "npm", "yarn": "npm", "pnpm": "npm"},
    "typescript": {"npm": "npm", "yarn": "npm", "pnpm": "npm"},
    "java": {"maven": "maven", "gradle": "gradle"},
    "kotlin": {"gradle": "gradle"},
    "go": {"go modules": "gomod"},
    "rust": {"cargo": "cargo"},
    "csharp": {"dotnet": "nuget"},
    "ruby": {"bundler": "bundler"},
}


def primary_ecosystem(project: ProjectProfile) -> Optional[str]:
    """The Dependabot package-ecosystem for the project's primary language, if known."""
    by_manager = _ECOSYSTEM_BY_LANG_AND_MANAGER.get(project.language, {})
    return by_manager.get(project.package_manager or "")
