"""Smart-default container profiles — maps a detected project to Dockerfile values.

Mirrors ci_onboard/profiles.py's shape (language defaults -> a fully-populated
profile dataclass ready for template rendering), but for container images
instead of CI pipelines: base/builder image, install/build commands, the
multi-stage copy step for compiled languages, run command, and port.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..ci_onboard.detector import ProjectProfile


@dataclass
class ContainerProfile:
    """All values needed by the Dockerfile / .dockerignore / compose Jinja2 templates."""

    language: str = "unknown"
    framework: Optional[str] = None
    runtime_version: str = "latest"

    multi_stage: bool = False
    builder_image: str = ""
    base_image: str = ""
    workdir: str = "/app"

    manifest_files: List[str] = field(default_factory=list)
    install_cmd: str = ""
    build_cmd: str = ""
    build_copy_from: str = ""
    build_copy_to: str = ""
    runtime_extra: str = ""

    run_cmd: List[str] = field(default_factory=list)
    port: int = 8080
    service_name: str = "app"

    def as_dict(self) -> Dict[str, Any]:
        """Return all fields as a dict for Jinja2 rendering."""
        return {
            "language": self.language,
            "framework": self.framework or "",
            "runtime_version": self.runtime_version,
            "multi_stage": self.multi_stage,
            "builder_image": self.builder_image,
            "base_image": self.base_image,
            "workdir": self.workdir,
            "manifest_files": self.manifest_files,
            "install_cmd": self.install_cmd,
            "build_cmd": self.build_cmd,
            "build_copy_from": self.build_copy_from,
            "build_copy_to": self.build_copy_to,
            "runtime_extra": self.runtime_extra,
            "run_cmd": self.run_cmd,
            "port": self.port,
            "service_name": self.service_name,
        }


# ---------------------------------------------------------------------------
# Language-specific defaults
# ---------------------------------------------------------------------------
# Lock/manifest files with a trailing "*" are copied via a wildcard so the
# COPY step doesn't fail the build when that file legitimately doesn't exist
# yet (e.g. a go.mod with no dependencies has no go.sum) — the standard
# "COPY go.mod go.sum* ./" idiom, generalized to every language here.

_LANG_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "python": {
        "base_image": "python:{version}-slim",
        "default_version": "3.12",
        "multi_stage": False,
        "manifest_files_by_manager": {
            "pip": ["requirements.txt"],
            "poetry": ["pyproject.toml", "poetry.lock*"],
            "pipenv": ["Pipfile", "Pipfile.lock*"],
        },
        "install_by_manager": {
            "pip": "pip install --no-cache-dir -r requirements.txt",
            "poetry": "pip install --no-cache-dir poetry && poetry install --no-interaction --no-root",
            "pipenv": "pip install --no-cache-dir pipenv && pipenv install --deploy --system",
        },
        "run_cmd_by_framework": {
            "django": ["python", "manage.py", "runserver", "0.0.0.0:{port}"],
            "flask": ["flask", "run", "--host=0.0.0.0", "--port={port}"],
            "fastapi": ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"],
        },
        "default_run_cmd": ["python", "app.py"],
        "port_by_framework": {"django": 8000, "flask": 5000, "fastapi": 8000},
        "default_port": 8000,
    },
    "javascript": {
        "base_image": "node:{version}-slim",
        "default_version": "20",
        "multi_stage": False,
        "manifest_files_by_manager": {
            "npm": ["package.json", "package-lock.json*"],
            "yarn": ["package.json", "yarn.lock*"],
            "pnpm": ["package.json", "pnpm-lock.yaml*"],
        },
        "install_by_manager": {
            "npm": "npm ci --omit=dev",
            "yarn": "yarn install --frozen-lockfile --production",
            "pnpm": "corepack enable && pnpm install --frozen-lockfile --prod",
        },
        "run_cmd_by_framework": {
            "nextjs": ["npm", "start"],
            "express": ["node", "index.js"],
        },
        "default_run_cmd": ["npm", "start"],
        "port_by_framework": {"nextjs": 3000, "express": 3000},
        "default_port": 3000,
    },
    "typescript": {
        "base_image": "node:{version}-slim",
        "default_version": "20",
        "multi_stage": False,
        "manifest_files_by_manager": {
            "npm": ["package.json", "package-lock.json*"],
            "yarn": ["package.json", "yarn.lock*"],
            "pnpm": ["package.json", "pnpm-lock.yaml*"],
        },
        # Full install (incl. devDependencies) is needed here — the build
        # step below (tsc) is itself usually a devDependency.
        "install_by_manager": {
            "npm": "npm ci",
            "yarn": "yarn install --frozen-lockfile",
            "pnpm": "corepack enable && pnpm install --frozen-lockfile",
        },
        "build_cmd": "npm run build",
        "run_cmd_by_framework": {
            "nextjs": ["npm", "start"],
        },
        "default_run_cmd": ["node", "dist/index.js"],
        "port_by_framework": {"nextjs": 3000},
        "default_port": 3000,
    },
    "java": {
        "base_image": "eclipse-temurin:{version}-jre",
        "builder_image": "eclipse-temurin:{version}-jdk",
        "default_version": "21",
        "multi_stage": True,
        "manifest_files_by_manager": {
            "maven": ["pom.xml"],
            "gradle": ["build.gradle", "settings.gradle*"],
        },
        "install_by_manager": {
            "maven": "mvn -q dependency:go-offline",
            "gradle": "./gradlew dependencies --no-daemon",
        },
        "build_cmd_by_manager": {
            "maven": "mvn -q package -DskipTests",
            "gradle": "./gradlew build -x test --no-daemon",
        },
        "build_copy_from_by_manager": {
            "maven": "/app/target/*.jar",
            "gradle": "/app/build/libs/*.jar",
        },
        "build_copy_to": "/app/app.jar",
        "default_run_cmd": ["java", "-jar", "/app/app.jar"],
        "default_port": 8080,
    },
    "kotlin": {
        "base_image": "eclipse-temurin:{version}-jre",
        "builder_image": "eclipse-temurin:{version}-jdk",
        "default_version": "21",
        "multi_stage": True,
        "manifest_files_by_manager": {
            "gradle": ["build.gradle.kts", "settings.gradle.kts*"],
        },
        "install_by_manager": {
            "gradle": "./gradlew dependencies --no-daemon",
        },
        "build_cmd_by_manager": {
            "gradle": "./gradlew build -x test --no-daemon",
        },
        "build_copy_from_by_manager": {
            "gradle": "/app/build/libs/*.jar",
        },
        "build_copy_to": "/app/app.jar",
        "default_run_cmd": ["java", "-jar", "/app/app.jar"],
        "default_port": 8080,
    },
    "go": {
        "base_image": "alpine:3.19",
        "builder_image": "golang:{version}",
        "default_version": "1.22",
        "multi_stage": True,
        "manifest_files_by_manager": {
            "go modules": ["go.mod", "go.sum*"],
        },
        "install_by_manager": {
            "go modules": "go mod download",
        },
        "build_cmd_by_manager": {
            "go modules": "CGO_ENABLED=0 go build -o /out/app ./...",
        },
        "build_copy_from_by_manager": {
            "go modules": "/out/app",
        },
        "build_copy_to": "/app/app",
        "default_run_cmd": ["/app/app"],
        "default_port": 8080,
        "runtime_extra": "RUN apk add --no-cache ca-certificates",
    },
    "rust": {
        "base_image": "debian:bookworm-slim",
        "builder_image": "rust:{version}",
        "default_version": "1",
        "multi_stage": True,
        "manifest_files_by_manager": {
            "cargo": ["Cargo.toml", "Cargo.lock*"],
        },
        "install_by_manager": {
            "cargo": "cargo fetch",
        },
        "build_cmd_by_manager": {
            "cargo": "cargo build --release",
        },
        # {binary_name} resolved at profile-build time from Cargo.toml (or
        # falls back to the project directory name).
        "build_copy_from_by_manager": {
            "cargo": "/app/target/release/{binary_name}",
        },
        "build_copy_to": "/app/app",
        "default_run_cmd": ["/app/app"],
        "default_port": 8080,
        "runtime_extra": (
            "RUN apt-get update && apt-get install -y --no-install-recommends "
            "ca-certificates && rm -rf /var/lib/apt/lists/*"
        ),
    },
    "csharp": {
        "base_image": "mcr.microsoft.com/dotnet/aspnet:{version}",
        "builder_image": "mcr.microsoft.com/dotnet/sdk:{version}",
        "default_version": "8.0",
        "multi_stage": True,
        "manifest_files_by_manager": {
            "dotnet": ["*.csproj"],
        },
        "install_by_manager": {
            "dotnet": "dotnet restore",
        },
        "build_cmd_by_manager": {
            "dotnet": "dotnet publish -c Release -o /out/publish",
        },
        "build_copy_from_by_manager": {
            "dotnet": "/out/publish",
        },
        "build_copy_to": "/app",
        # {assembly_name} resolved at profile-build time from the first
        # *.csproj file's name (falls back to the project directory name).
        "default_run_cmd": ["dotnet", "{assembly_name}.dll"],
        "default_port": 8080,
    },
    "ruby": {
        "base_image": "ruby:{version}-slim",
        "default_version": "3.3",
        "multi_stage": False,
        "manifest_files_by_manager": {
            "bundler": ["Gemfile", "Gemfile.lock*"],
        },
        "install_by_manager": {
            "bundler": (
                "apt-get update && apt-get install -y --no-install-recommends build-essential "
                "&& bundle install --jobs=4 "
                "&& apt-get purge -y build-essential && rm -rf /var/lib/apt/lists/*"
            ),
        },
        "run_cmd_by_framework": {
            "rails": ["bin/rails", "server", "-b", "0.0.0.0", "-p", "{port}"],
        },
        "default_run_cmd": ["ruby", "app.rb"],
        "port_by_framework": {"rails": 3000},
        "default_port": 3000,
    },
}

_GENERIC_FALLBACK: Dict[str, Any] = {
    "base_image": "debian:bookworm-slim",
    "default_version": "",
    "multi_stage": False,
    "manifest_files_by_manager": {},
    "install_by_manager": {},
    "default_run_cmd": ["echo", "TODO: set the container's start command"],
    "default_port": 8080,
}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return slug or "app"


def _parse_rust_binary_name(project_path: str) -> Optional[str]:
    cargo_toml = Path(project_path) / "Cargo.toml"
    if not cargo_toml.exists():
        return None
    text = cargo_toml.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'(?m)^\s*name\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else None


def _parse_dotnet_assembly_name(project_path: str) -> Optional[str]:
    csproj_files = sorted(Path(project_path).glob("*.csproj"))
    return csproj_files[0].stem if csproj_files else None


def get_container_profile(
    project: ProjectProfile,
    project_path: str,
    port: Optional[int] = None,
) -> ContainerProfile:
    """Merge detected project info with language/container smart defaults.

    Returns a fully-populated ContainerProfile ready for template rendering.
    Unknown languages fall back to a generic, always-valid-but-manual-review
    profile rather than raising — containerization should never hard-fail
    just because a language wasn't recognized.
    """
    lang = project.language
    defaults = _LANG_DEFAULTS.get(lang, _GENERIC_FALLBACK)
    mgr = project.package_manager or ""

    version = project.runtime_version or defaults.get("default_version", "latest")

    def _fmt(image_tmpl: str) -> str:
        return image_tmpl.replace("{version}", version) if image_tmpl else ""

    multi_stage = bool(defaults.get("multi_stage", False))
    base_image = _fmt(defaults.get("base_image", ""))
    builder_image = _fmt(defaults.get("builder_image", ""))

    manifest_files = list(defaults.get("manifest_files_by_manager", {}).get(mgr, []))
    install_cmd = defaults.get("install_by_manager", {}).get(mgr, "")

    if multi_stage:
        build_cmd = defaults.get("build_cmd_by_manager", {}).get(mgr, "")
        build_copy_from = defaults.get("build_copy_from_by_manager", {}).get(mgr, defaults.get("build_copy_from", ""))
        build_copy_to = defaults.get("build_copy_to", "")
    else:
        build_cmd = defaults.get("build_cmd", "")
        build_copy_from = ""
        build_copy_to = ""

    framework = project.framework
    run_cmd_template = defaults.get("run_cmd_by_framework", {}).get(framework, defaults.get("default_run_cmd", []))
    resolved_port = port or defaults.get("port_by_framework", {}).get(framework) or defaults.get("default_port", 8080)
    run_cmd = [tok.replace("{port}", str(resolved_port)) for tok in run_cmd_template]

    if lang == "rust" and build_copy_from:
        binary_name = _parse_rust_binary_name(project_path) or Path(project_path).resolve().name
        build_copy_from = build_copy_from.replace("{binary_name}", binary_name)

    if lang == "csharp":
        assembly_name = _parse_dotnet_assembly_name(project_path) or Path(project_path).resolve().name
        run_cmd = [tok.replace("{assembly_name}", assembly_name) for tok in run_cmd]

    return ContainerProfile(
        language=lang,
        framework=framework,
        runtime_version=version,
        multi_stage=multi_stage,
        builder_image=builder_image,
        base_image=base_image,
        workdir="/app",
        manifest_files=manifest_files,
        install_cmd=install_cmd,
        build_cmd=build_cmd,
        build_copy_from=build_copy_from,
        build_copy_to=build_copy_to,
        runtime_extra=defaults.get("runtime_extra", ""),
        run_cmd=run_cmd,
        port=resolved_port,
        service_name=_slugify(Path(project_path).resolve().name),
    )
