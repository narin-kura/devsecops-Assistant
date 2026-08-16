"""Project detector — scans a directory and infers language, framework, and tooling."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ...logging_utils import get_logger

log = get_logger(__name__)


@dataclass
class ProjectProfile:
    """Everything the onboarding engine needs to know about a project."""

    language: str = "unknown"
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    has_tests: bool = False
    has_docker: bool = False
    has_lint_config: bool = False
    has_security_scan: bool = False
    entry_point: Optional[str] = None
    runtime_version: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def summary_lines(self) -> List[str]:
        """Human-readable summary of detected profile."""
        lines = [
            f"  Language        : {self.language}",
            f"  Framework       : {self.framework or '—'}",
            f"  Package manager : {self.package_manager or '—'}",
            f"  Has tests       : {'yes' if self.has_tests else 'no'}",
            f"  Has Dockerfile  : {'yes' if self.has_docker else 'no'}",
            f"  Linter config   : {'yes' if self.has_lint_config else 'no'}",
        ]
        if self.runtime_version:
            lines.append(f"  Runtime version : {self.runtime_version}")
        return lines


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def _detect_python(root: Path, profile: ProjectProfile) -> bool:
    """Detect Python project signals."""
    markers = {
        "requirements.txt": "pip",
        "Pipfile": "pipenv",
        "pyproject.toml": "poetry",
        "setup.py": "pip",
        "setup.cfg": "pip",
    }
    found_manager = None
    for marker, mgr in markers.items():
        if (root / marker).exists():
            found_manager = mgr
            break

    if found_manager is None:
        return False

    profile.language = "python"
    profile.package_manager = found_manager

    # Prefer pyproject.toml poetry over pip if both exist
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        if "[tool.poetry]" in text:
            profile.package_manager = "poetry"

    # Framework detection from requirements / pyproject
    _detect_python_framework(root, profile)

    # Tests
    for test_dir in ("tests", "test", "spec"):
        if (root / test_dir).is_dir():
            profile.has_tests = True
            break
    if not profile.has_tests and (root / "pytest.ini").exists():
        profile.has_tests = True
    if not profile.has_tests and (root / "tox.ini").exists():
        profile.has_tests = True

    # Lint
    for lint_file in (".flake8", ".pylintrc", "mypy.ini", ".ruff.toml", "ruff.toml"):
        if (root / lint_file).exists():
            profile.has_lint_config = True
            break
    if not profile.has_lint_config and pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        if "[tool.ruff]" in text or "[tool.pylint]" in text or "[tool.mypy]" in text:
            profile.has_lint_config = True

    # Runtime version
    if (root / ".python-version").exists():
        profile.runtime_version = (root / ".python-version").read_text().strip()
    elif (root / "runtime.txt").exists():
        profile.runtime_version = (root / "runtime.txt").read_text().strip()

    return True


def _detect_python_framework(root: Path, profile: ProjectProfile) -> None:
    """Try to identify Django / Flask / FastAPI from dependency files."""
    dep_text = ""
    for dep_file in ("requirements.txt", "Pipfile", "pyproject.toml", "setup.cfg"):
        fp = root / dep_file
        if fp.exists():
            dep_text += fp.read_text(encoding="utf-8", errors="ignore")

    dep_lower = dep_text.lower()
    if "django" in dep_lower:
        profile.framework = "django"
    elif "fastapi" in dep_lower:
        profile.framework = "fastapi"
    elif "flask" in dep_lower:
        profile.framework = "flask"


def _detect_node(root: Path, profile: ProjectProfile) -> bool:
    """Detect Node.js / JavaScript / TypeScript project."""
    pkg_json = root / "package.json"
    if not pkg_json.exists():
        return False

    profile.language = "javascript"

    # TypeScript?
    if (root / "tsconfig.json").exists():
        profile.language = "typescript"

    # Package manager
    if (root / "pnpm-lock.yaml").exists():
        profile.package_manager = "pnpm"
    elif (root / "yarn.lock").exists():
        profile.package_manager = "yarn"
    else:
        profile.package_manager = "npm"

    try:
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pkg = {}

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    # Framework
    if "next" in deps:
        profile.framework = "nextjs"
    elif "nuxt" in deps or "nuxt3" in deps:
        profile.framework = "nuxt"
    elif "@angular/core" in deps:
        profile.framework = "angular"
    elif "vue" in deps:
        profile.framework = "vue"
    elif "react" in deps:
        profile.framework = "react"
    elif "express" in deps:
        profile.framework = "express"

    # Tests
    scripts = pkg.get("scripts", {})
    if "test" in scripts and scripts["test"] not in ("", 'echo "Error: no test specified" && exit 1'):
        profile.has_tests = True
    for td in ("__tests__", "tests", "test", "spec"):
        if (root / td).is_dir():
            profile.has_tests = True

    # Lint
    if "eslint" in deps or (root / ".eslintrc.json").exists() or (root / ".eslintrc.js").exists():
        profile.has_lint_config = True

    # Entry point
    profile.entry_point = pkg.get("main")

    return True


def _detect_java(root: Path, profile: ProjectProfile) -> bool:
    """Detect Java / Kotlin project (Maven or Gradle)."""
    if (root / "pom.xml").exists():
        profile.language = "java"
        profile.package_manager = "maven"
    elif (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
        profile.language = "java"
        profile.package_manager = "gradle"
        if (root / "build.gradle.kts").exists():
            profile.language = "kotlin"
    else:
        return False

    # Spring detection
    sources = ""
    if (root / "pom.xml").exists():
        sources = (root / "pom.xml").read_text(encoding="utf-8", errors="ignore")
    for gf in ("build.gradle", "build.gradle.kts"):
        if (root / gf).exists():
            sources += (root / gf).read_text(encoding="utf-8", errors="ignore")
    if "spring" in sources.lower():
        profile.framework = "spring"

    # Tests
    for td in ("src/test", "src/test/java", "src/test/kotlin"):
        if (root / td).is_dir():
            profile.has_tests = True
            break

    return True


def _detect_go(root: Path, profile: ProjectProfile) -> bool:
    """Detect Go project."""
    if not (root / "go.mod").exists():
        return False
    profile.language = "go"
    profile.package_manager = "go modules"

    # Tests — look for *_test.go files
    for f in root.rglob("*_test.go"):
        profile.has_tests = True
        break

    # Lint
    if (root / ".golangci.yml").exists() or (root / ".golangci.yaml").exists():
        profile.has_lint_config = True

    return True


def _detect_rust(root: Path, profile: ProjectProfile) -> bool:
    """Detect Rust project."""
    if not (root / "Cargo.toml").exists():
        return False
    profile.language = "rust"
    profile.package_manager = "cargo"
    profile.has_tests = True  # cargo test is built-in
    return True


def _detect_dotnet(root: Path, profile: ProjectProfile) -> bool:
    """Detect .NET / C# project."""
    csproj = list(root.glob("*.csproj"))
    sln = list(root.glob("*.sln"))
    if not csproj and not sln:
        return False
    profile.language = "csharp"
    profile.package_manager = "dotnet"

    # Check for ASP.NET
    for cp in csproj:
        text = cp.read_text(encoding="utf-8", errors="ignore")
        if "Microsoft.AspNetCore" in text:
            profile.framework = "aspnet"
            break

    # Tests
    test_dirs = list(root.glob("*.Tests")) + list(root.glob("*Test*"))
    if test_dirs:
        profile.has_tests = True

    return True


def _detect_ruby(root: Path, profile: ProjectProfile) -> bool:
    """Detect Ruby project."""
    if not (root / "Gemfile").exists():
        return False
    profile.language = "ruby"
    profile.package_manager = "bundler"

    gemfile_text = (root / "Gemfile").read_text(encoding="utf-8", errors="ignore")
    if "rails" in gemfile_text.lower():
        profile.framework = "rails"

    for td in ("test", "spec"):
        if (root / td).is_dir():
            profile.has_tests = True
            break

    if (root / ".rubocop.yml").exists():
        profile.has_lint_config = True

    return True


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_DETECTORS = [
    _detect_python,
    _detect_node,
    _detect_java,
    _detect_go,
    _detect_rust,
    _detect_dotnet,
    _detect_ruby,
]


def detect(project_path: str) -> ProjectProfile:
    """Scan *project_path* and return a populated ProjectProfile.

    Detectors are tried in order; the first match wins.
    Docker and security-scan flags are checked independently.
    """
    root = Path(project_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project_path}")

    profile = ProjectProfile()

    for detector in _DETECTORS:
        if detector(root, profile):
            log.info("Detected %s project (%s)", profile.language, detector.__name__)
            break
    else:
        log.warning("Could not auto-detect project language in %s", root)

    # Docker (language-independent)
    if (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
        profile.has_docker = True

    return profile
