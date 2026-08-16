"""Smart-default pipeline profiles — maps (language, ci_tool) to template values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .detector import ProjectProfile


@dataclass
class PipelineProfile:
    """All values needed by the Jinja2 CI templates."""

    # Project basics
    language: str = "unknown"
    framework: Optional[str] = None
    runtime_version: str = "latest"

    # Commands
    install_cmd: str = ""
    build_cmd: str = ""
    test_cmd: str = ""
    lint_cmd: str = ""
    security_cmd: str = ""

    # Flags
    has_tests: bool = False
    has_docker: bool = False
    has_lint: bool = False
    has_security_scan: bool = True  # DevSecOps default: always on

    # CI-specific
    ci_tool: str = ""
    docker_image: str = ""
    deploy_branch: str = "main"
    artifact_paths: List[str] = field(default_factory=list)
    cache_paths: List[str] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Return all fields as a dict for Jinja2 rendering."""
        return {
            "language": self.language,
            "framework": self.framework or "",
            "runtime_version": self.runtime_version,
            "install_cmd": self.install_cmd,
            "build_cmd": self.build_cmd,
            "test_cmd": self.test_cmd,
            "lint_cmd": self.lint_cmd,
            "security_cmd": self.security_cmd,
            "has_tests": self.has_tests,
            "has_docker": self.has_docker,
            "has_lint": self.has_lint,
            "has_security_scan": self.has_security_scan,
            "ci_tool": self.ci_tool,
            "docker_image": self.docker_image,
            "deploy_branch": self.deploy_branch,
            "artifact_paths": self.artifact_paths,
            "cache_paths": self.cache_paths,
            "env_vars": self.env_vars,
        }


# ---------------------------------------------------------------------------
# Language-specific defaults
# ---------------------------------------------------------------------------

_LANG_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "python": {
        "docker_image": "python:{version}",
        "default_version": "3.12",
        "install": {
            "pip": "pip install --upgrade pip && pip install -r requirements.txt",
            "poetry": "pip install poetry && poetry install --no-interaction",
            "pipenv": "pip install pipenv && pipenv install --dev",
        },
        "build_cmd": "",
        "test_cmd": "pytest --tb=short -q",
        "lint_cmd": "ruff check . || flake8 .",
        "security_cmd": "pip install safety && safety check",
        "cache_paths": [".venv", "__pycache__"],
    },
    "javascript": {
        "docker_image": "node:{version}",
        "default_version": "20",
        "install": {
            "npm": "npm ci",
            "yarn": "yarn install --frozen-lockfile",
            "pnpm": "pnpm install --frozen-lockfile",
        },
        "build_cmd": "npm run build --if-present",
        "test_cmd": "npm test",
        "lint_cmd": "npx eslint . --max-warnings=0",
        "security_cmd": "npm audit --audit-level=high",
        "cache_paths": ["node_modules", ".npm"],
    },
    "typescript": {
        "docker_image": "node:{version}",
        "default_version": "20",
        "install": {
            "npm": "npm ci",
            "yarn": "yarn install --frozen-lockfile",
            "pnpm": "pnpm install --frozen-lockfile",
        },
        "build_cmd": "npm run build",
        "test_cmd": "npm test",
        "lint_cmd": "npx eslint . --max-warnings=0",
        "security_cmd": "npm audit --audit-level=high",
        "cache_paths": ["node_modules", ".npm"],
    },
    "java": {
        "docker_image": "eclipse-temurin:{version}",
        "default_version": "21",
        "install": {
            "maven": "mvn dependency:resolve",
            "gradle": "./gradlew dependencies",
        },
        "build_cmd_map": {
            "maven": "mvn package -DskipTests",
            "gradle": "./gradlew build -x test",
        },
        "test_cmd_map": {
            "maven": "mvn test",
            "gradle": "./gradlew test",
        },
        "lint_cmd": "",
        "security_cmd_map": {
            "maven": "mvn org.owasp:dependency-check-maven:check",
            "gradle": "./gradlew dependencyCheckAnalyze",
        },
        "cache_paths": [".m2/repository", ".gradle"],
    },
    "kotlin": {
        "docker_image": "eclipse-temurin:{version}",
        "default_version": "21",
        "install": {
            "gradle": "./gradlew dependencies",
        },
        "build_cmd": "./gradlew build -x test",
        "test_cmd": "./gradlew test",
        "lint_cmd": "./gradlew ktlintCheck",
        "security_cmd": "./gradlew dependencyCheckAnalyze",
        "cache_paths": [".gradle"],
    },
    "go": {
        "docker_image": "golang:{version}",
        "default_version": "1.22",
        "install": {"go modules": "go mod download"},
        "build_cmd": "go build ./...",
        "test_cmd": "go test ./... -v",
        "lint_cmd": "golangci-lint run",
        "security_cmd": "go install golang.org/x/vuln/cmd/govulncheck@latest && govulncheck ./...",
        "cache_paths": ["~/go/pkg/mod"],
    },
    "rust": {
        "docker_image": "rust:{version}",
        "default_version": "latest",
        "install": {"cargo": "cargo fetch"},
        "build_cmd": "cargo build --release",
        "test_cmd": "cargo test",
        "lint_cmd": "cargo clippy -- -D warnings",
        "security_cmd": "cargo install cargo-audit && cargo audit",
        "cache_paths": ["~/.cargo/registry", "target"],
    },
    "csharp": {
        "docker_image": "mcr.microsoft.com/dotnet/sdk:{version}",
        "default_version": "8.0",
        "install": {"dotnet": "dotnet restore"},
        "build_cmd": "dotnet build --configuration Release --no-restore",
        "test_cmd": "dotnet test --no-build --configuration Release",
        "lint_cmd": "",
        "security_cmd": "dotnet list package --vulnerable --include-transitive",
        "cache_paths": ["~/.nuget/packages"],
    },
    "ruby": {
        "docker_image": "ruby:{version}",
        "default_version": "3.3",
        "install": {"bundler": "bundle install --jobs=4"},
        "build_cmd": "",
        "test_cmd": "bundle exec rake test",
        "lint_cmd": "bundle exec rubocop",
        "security_cmd": "gem install bundler-audit && bundle-audit check --update",
        "cache_paths": ["vendor/bundle"],
    },
}


def get_profile(project: ProjectProfile, ci_tool: str, deploy_branch: str = "main") -> PipelineProfile:
    """Merge detected project info with language/CI smart defaults.

    Returns a fully-populated PipelineProfile ready for template rendering.
    """
    lang = project.language
    defaults = _LANG_DEFAULTS.get(lang, {})
    mgr = project.package_manager or ""

    # Resolve runtime version
    version = project.runtime_version or defaults.get("default_version", "latest")

    # Resolve docker image
    docker_image = defaults.get("docker_image", "")
    if docker_image and "{version}" in docker_image:
        docker_image = docker_image.replace("{version}", version)

    # Resolve install command
    install_map = defaults.get("install", {})
    install_cmd = install_map.get(mgr, "") if isinstance(install_map, dict) else ""

    # Build / test / lint / security — may have per-manager maps
    def _resolve(key: str) -> str:
        map_key = f"{key}_map"
        if map_key in defaults:
            return defaults[map_key].get(mgr, "")
        return defaults.get(key, "")

    build_cmd = _resolve("build_cmd")
    test_cmd = _resolve("test_cmd")
    lint_cmd = _resolve("lint_cmd")
    security_cmd = _resolve("security_cmd")

    return PipelineProfile(
        language=lang,
        framework=project.framework,
        runtime_version=version,
        install_cmd=install_cmd,
        build_cmd=build_cmd,
        test_cmd=test_cmd if project.has_tests else "",
        lint_cmd=lint_cmd if project.has_lint_config else "",
        security_cmd=security_cmd,
        has_tests=project.has_tests,
        has_docker=project.has_docker,
        has_lint=project.has_lint_config,
        has_security_scan=True,
        ci_tool=ci_tool,
        docker_image=docker_image,
        deploy_branch=deploy_branch,
        cache_paths=defaults.get("cache_paths", []),
    )
