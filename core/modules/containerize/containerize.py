"""Containerization engine — orchestrates detection -> container profile -> rendering.

`containerize()` is pure compute-and-write, mirroring ci_onboard/onboard.py's
shape: it takes inputs, returns a structured result, and does no printing.
That keeps it callable from the CLI *and* from an agent tool wrapper without
either one fighting the other's output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ...logging_utils import get_logger
from ..ci_onboard.detector import detect, ProjectProfile
from .container_profiles import get_container_profile, ContainerProfile

log = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_DOCKERFILE_TEMPLATE = "Dockerfile.j2"
_DOCKERIGNORE_TEMPLATE = "dockerignore.j2"
_COMPOSE_TEMPLATE = "docker_compose.yml.j2"


@dataclass
class ContainerizeResult:
    """Structured outcome of a containerization run — no printing baked in."""

    project: ProjectProfile
    container: ContainerProfile
    dockerfile_rendered: str
    dockerignore_rendered: str
    compose_rendered: Optional[str]
    dry_run: bool
    dockerfile_path: Optional[Path] = None
    dockerignore_path: Optional[Path] = None
    compose_path: Optional[Path] = None


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )


def containerize(
    project_path: str,
    port: Optional[int] = None,
    output_path: Optional[str] = None,
    include_compose: bool = False,
    dry_run: bool = False,
) -> ContainerizeResult:
    """Run the full containerization pipeline and return a structured result.

    1. Detect project profile
    2. Build container profile with smart defaults (base image, run command, port)
    3. Render Dockerfile + .dockerignore (+ docker-compose.yml if requested)
    4. Write the result to disk, unless *dry_run* is set
    """
    log.info("Scanning project at %s for containerization…", project_path)
    project = detect(project_path)
    container = get_container_profile(project, project_path, port=port)

    env = _env()
    dockerfile_rendered = env.get_template(_DOCKERFILE_TEMPLATE).render(**container.as_dict())
    dockerignore_rendered = env.get_template(_DOCKERIGNORE_TEMPLATE).render(**container.as_dict())

    compose_rendered = None
    if include_compose:
        compose_rendered = env.get_template(_COMPOSE_TEMPLATE).render(
            service_name=container.service_name, port=container.port
        )

    result = ContainerizeResult(
        project=project,
        container=container,
        dockerfile_rendered=dockerfile_rendered,
        dockerignore_rendered=dockerignore_rendered,
        compose_rendered=compose_rendered,
        dry_run=dry_run,
    )

    if not dry_run:
        root = Path(project_path).resolve()
        dockerfile_dest = Path(output_path) if output_path else root / "Dockerfile"
        dockerfile_dest.parent.mkdir(parents=True, exist_ok=True)
        dockerfile_dest.write_text(dockerfile_rendered, encoding="utf-8")
        result.dockerfile_path = dockerfile_dest

        dockerignore_dest = dockerfile_dest.parent / ".dockerignore"
        dockerignore_dest.write_text(dockerignore_rendered, encoding="utf-8")
        result.dockerignore_path = dockerignore_dest

        if include_compose:
            compose_dest = dockerfile_dest.parent / "docker-compose.yml"
            compose_dest.write_text(compose_rendered, encoding="utf-8")
            result.compose_path = compose_dest

    return result


def format_report(result: ContainerizeResult) -> str:
    """Render a human-readable report for *result* — CLI presentation only."""
    lines = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║      DevSecOps Assistant — Containerization          ║",
        "╚══════════════════════════════════════════════════════╝",
        "",
        "🔍 Detected project profile:",
        *result.project.summary_lines(),
        "",
        f"🐳 Base image  : {result.container.base_image}",
        f"🔌 Port        : {result.container.port}",
        "",
    ]

    if result.dry_run:
        lines.append("📄 Rendered Dockerfile:")
        lines.append("")
        lines.append("─" * 60)
        lines.append(result.dockerfile_rendered)
        lines.append("─" * 60)
        if result.compose_rendered:
            lines.append("")
            lines.append("📄 Rendered docker-compose.yml:")
            lines.append("─" * 60)
            lines.append(result.compose_rendered)
            lines.append("─" * 60)
    else:
        lines.append(f"✅ Dockerfile written to: {result.dockerfile_path}")
        lines.append(f"✅ .dockerignore written to: {result.dockerignore_path}")
        if result.compose_path:
            lines.append(f"✅ docker-compose.yml written to: {result.compose_path}")
        lines.append("")
        lines.append("📋 Next steps:")
        lines.append(f"   1. Review the CMD and EXPOSE port ({result.container.port}) — auto-detected, not guaranteed")
        lines.append("   2. Build it: docker build -t <name> .")
        lines.append(f"   3. Run it:   docker run -p {result.container.port}:{result.container.port} <name>")

    return "\n".join(lines)


def containerize_cli(args) -> int:
    """CLI entry point for the containerize subcommand."""
    try:
        result = containerize(
            project_path=args.project,
            port=args.port,
            output_path=args.output,
            include_compose=args.compose,
            dry_run=args.dry_run,
        )
        print(format_report(result))
        return 0
    except Exception as exc:
        log.error("Containerization failed: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1
